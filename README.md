# 🎓 Exam Paper Pattern Predictor (No-Database, Simple Edition)

[![License: MIT](https://img.shields.libs.im/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.libs.im/badge/Node.js-v18+-green.svg)](https://nodejs.org/)
[![Python](https://img.libs.im/badge/Python-3.8+-blue.svg)](https://www.python.org/)

An AI-powered web tool designed for students to analyze previous years' university question papers (PYQs). Just upload your past papers (either as multiple separate files or a single merged PDF) and type in your subject to instantly identify high-frequency questions, predict topic probabilities, and explore GATE syllabus alignment.

All of this happens **entirely in memory** on the server—no databases, no user registration, and no storage of personal credentials.

---

## ✨ Key Features

1. **🔁 Repeating Question Finder**: Finds exact and semantically similar questions across multiple papers and sorts them by frequency.
2. **🔀 Smart Merged PDF Slicing**: Automatically detects different year sections within a single merged PDF file by scanning text for year serials (e.g. `MS'23`, `RS'22`, `19/7546`) and partitions the document into individual exams.
3. **📊 Interactive Topic Frequency & Probability Chart**: Renders dynamic bar charts using Chart.js, indicating topic importance and probability bands (Very High, High, Medium, Low).
4. **🔍 Interactive Search Bar**: Search and filter repeating questions instantly with matching keyword highlighting.
5. **📋 Copy-to-Clipboard**: Copy individual questions directly with one click.
6. **📥 Download PDF Report**: Exports a professional dark-themed 4-page analysis report (including cover page, repeating questions table, and GATE analysis) using jsPDF AutoTable.
7. **🎓 GATE Exam Alignment**: Automatically parses standard CS subjects (like OS, DBMS, CN, DSA, TOC, CD, COA, DM) against their GATE syllabus frequency and outlines sample exam questions.

---

## 🛠️ Tech Stack

* **Frontend**: HTML5, CSS3 (Glassmorphism & animations), JavaScript (ES6+), Chart.js, jsPDF & jsPDF AutoTable.
* **Backend**: Node.js, Express.js (routing & parsing), Multer (temp memory storage).
* **ML / Processing**: Python 3, pdfplumber (text extraction), standard library logic (Jaccard similarity string matching).

---

## 📁 Project Structure

```
simple-predictor/
├── server.js            # Node.js backend (spawns Python via spawnSync)
├── analyse.py           # Python analysis engine (Page year detector, text clean, matching)
├── package.json         # Node dependencies (express, multer, cors)
├── requirements.txt     # Python requirements (pdfplumber)
├── public/
│   └── index.html       # Full SPA UI, styles, charts, and client-side PDF export
└── uploads/             # Temp upload directory
```

---

## 🚀 Getting Started

### Prerequisites

* [Node.js](https://nodejs.org/) (v18+)
* [Python 3](https://www.python.org/) (Ensure it is added to your environment `PATH`)

### Installation & Run

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Aryan-Lade/Exam-Paper-Pattern-Predictor.git
   cd Exam-Paper-Pattern-Predictor
   ```

2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Install Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the application**:
   ```bash
   npm start
   ```

5. **Open in browser**:
   Visit **`http://localhost:3000`** in your browser.

---

## 🔒 Security & Privacy

* **No Database**: We do not store any records of who uploads the papers or what subject names are analyzed.
* **Local Temp Storage**: Uploaded files are deleted automatically from the server memory immediately after the analysis finishes.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.
