/**
 * server.js — Simple Express backend
 * No database, no auth, no Cloudinary.
 * Accepts PDF uploads → runs Python → returns JSON analysis.
 *
 * FIX: Uses spawnSync with shell:false to avoid Windows cmd.exe ETIMEDOUT
 * caused by spaces in the project path.
 */

const express = require('express');
const multer  = require('multer');
const path    = require('path');
const fs      = require('fs');
const { spawnSync } = require('child_process');  // ← key fix: spawnSync not execSync
const os      = require('os');

const app  = express();
const PORT = process.env.PORT || 3000;

// ─── Uploads folder ───────────────────────────────────────────────────────────
const UPLOADS_DIR = path.join(__dirname, 'uploads');
if (!fs.existsSync(UPLOADS_DIR)) {
  fs.mkdirSync(UPLOADS_DIR, { recursive: true });
}

// ─── Find Python executable (once at startup) ─────────────────────────────────
// On Windows the executable may be "python", "python3", or "py"
function findPython() {
  const candidates = ['python', 'python3', 'py'];
  for (const cmd of candidates) {
    // Use shell:true ONLY for this quick version check (no path concerns)
    const r = spawnSync(cmd, ['--version'], {
      encoding: 'utf8',
      timeout: 8000,
      shell: true,        // only safe here because we control the input exactly
    });
    if (r.status === 0 && (r.stdout || r.stderr)) {
      console.log(`[Python] Found: ${cmd} — ${(r.stdout || r.stderr).trim()}`);
      return cmd;
    }
  }
  return null;
}

const PYTHON_CMD = findPython();
if (!PYTHON_CMD) {
  console.error('\n❌  Python not found in PATH. Please install Python 3 and restart.\n');
}

// ─── Multer: disk storage, PDF only, max 20MB ─────────────────────────────────
const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOADS_DIR),
  filename: (req, file, cb) => {
    const unique = Date.now() + '-' + Math.round(Math.random() * 1e9);
    // Strip all characters that could cause shell/path issues
    const safe = file.originalname.replace(/[^a-zA-Z0-9.\-_]/g, '_');
    cb(null, unique + '-' + safe);
  },
});

const fileFilter = (req, file, cb) => {
  if (file.mimetype === 'application/pdf') {
    cb(null, true);
  } else {
    cb(new Error('Only PDF files are accepted'), false);
  }
};

const upload = multer({
  storage,
  fileFilter,
  limits: { fileSize: 20 * 1024 * 1024, files: 10 },
});

// ─── Serve frontend ───────────────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, 'public')));

// ─── Analysis endpoint ────────────────────────────────────────────────────────
app.post('/analyse', upload.array('papers', 10), (req, res) => {
  const uploadedFiles = req.files || [];
  const subject       = (req.body.subject || 'Unknown Subject').trim();
  let   configPath    = null;

  try {
    if (!PYTHON_CMD) {
      return res.status(500).json({
        success: false,
        error: 'Python is not installed or not found in PATH. Please install Python 3.',
      });
    }
    if (uploadedFiles.length === 0) {
      return res.status(400).json({ success: false, error: 'Please upload at least one PDF file.' });
    }
    if (!subject) {
      return res.status(400).json({ success: false, error: 'Subject name is required.' });
    }

    // Write config JSON to a safe temp path (no spaces)
    const config = {
      pdfs: uploadedFiles.map((f) => f.path),
      subject,
    };
    configPath = path.join(os.tmpdir(), `exam_cfg_${Date.now()}.json`);
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');

    const scriptPath = path.join(__dirname, 'analyse.py');

    console.log(`[Analyse] subject="${subject}" pdfs=${uploadedFiles.length} script="${scriptPath}"`);

    // ── KEY FIX: spawnSync with shell:false ────────────────────────────────
    // Bypasses cmd.exe entirely — no ETIMEDOUT from Windows shell spawning.
    // Arguments are passed as an array, so spaces in paths are handled natively.
    const result = spawnSync(PYTHON_CMD, [scriptPath, configPath], {
      encoding:  'utf8',
      timeout:   180000,              // 3 minutes
      maxBuffer: 10 * 1024 * 1024,   // 10 MB
      shell:     false,               // ← DO NOT use cmd.exe
      cwd:       __dirname,
      env: {
        ...process.env,
        PYTHONIOENCODING: 'utf-8',    // force UTF-8 stdout (fixes charmap error on Windows)
        PYTHONUTF8: '1',              // Python 3.7+ UTF-8 mode
      },
    });

    // Timeout / spawn error
    if (result.error) {
      const code = result.error.code || '';
      if (code === 'ETIMEDOUT') {
        return res.status(500).json({
          success: false,
          error: 'Analysis timed out (3 min limit). Try uploading a smaller or fewer PDFs.',
        });
      }
      if (code === 'ENOENT') {
        return res.status(500).json({
          success: false,
          error: `Python executable "${PYTHON_CMD}" not found. Re-install Python and ensure it is added to PATH.`,
        });
      }
      return res.status(500).json({ success: false, error: `Process error: ${result.error.message}` });
    }

    // Python non-zero exit
    if (result.status !== 0) {
      const stderr = (result.stderr || '').trim();
      // Try to read structured error from stdout first
      let structuredErr = null;
      try { structuredErr = JSON.parse((result.stdout || '').trim()); } catch {}
      if (structuredErr && structuredErr.error) {
        return res.status(500).json({ success: false, error: structuredErr.error });
      }
      return res.status(500).json({
        success: false,
        error: `Python analysis failed (exit ${result.status}): ${stderr.slice(0, 500) || 'Unknown error. Make sure pdfplumber is installed: pip install pdfplumber'}`,
      });
    }

    // Parse stdout JSON
    const rawOut = (result.stdout || '').trim();
    if (!rawOut) {
      return res.status(500).json({
        success: false,
        error: 'Python script produced no output. Make sure pdfplumber is installed: pip install pdfplumber',
      });
    }

    let analysisResult;
    try {
      analysisResult = JSON.parse(rawOut);
    } catch {
      return res.status(500).json({
        success: false,
        error: 'Failed to parse analysis output. Partial output: ' + rawOut.slice(0, 200),
      });
    }

    return res.json(analysisResult);

  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  } finally {
    // Always clean up uploaded PDFs and config file
    uploadedFiles.forEach((f) => { try { fs.unlinkSync(f.path); } catch {} });
    if (configPath) { try { fs.unlinkSync(configPath); } catch {} }
  }
});

// ─── Health check ─────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    python: PYTHON_CMD || 'NOT FOUND',
    message: PYTHON_CMD
      ? `Exam Pattern Predictor running (Python: ${PYTHON_CMD})`
      : 'Python not found — install Python 3',
  });
});

// ─── Global error handler ──────────────────────────────────────────────────────
app.use((err, req, res, next) => {
  if (err.code === 'LIMIT_FILE_SIZE')  return res.status(400).json({ success: false, error: 'File too large. Maximum 20MB per PDF.' });
  if (err.code === 'LIMIT_FILE_COUNT') return res.status(400).json({ success: false, error: 'Too many files. Maximum 10 PDFs at once.' });
  res.status(500).json({ success: false, error: err.message });
});

app.listen(PORT, () => {
  console.log(`\n🎓 Exam Pattern Predictor running at http://localhost:${PORT}`);
  console.log(`   Python: ${PYTHON_CMD || '❌ NOT FOUND — install Python 3'}`);
  console.log(`   Open the URL in your browser to start analysing!\n`);
});
