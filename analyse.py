"""
analyse.py — Core ML engine for Exam Pattern Predictor
No pandas, no numpy. Uses only pdfplumber + Python stdlib.

Called by Node.js:  python analyse.py <config_json_path>
Config JSON:        { "pdfs": ["path1.pdf", ...], "subject": "DBMS" }
Outputs JSON to stdout.

Supports:
  - Multiple separate PDFs  (each = one paper)
  - Single merged PDF       (auto-detected year sections = individual papers)
"""

import sys
import json
import re
import os
import collections
import difflib

try:
    import pdfplumber
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "pdfplumber not installed. Run: pip install pdfplumber"
    }))
    sys.exit(1)


# ─── GATE Subject Database ────────────────────────────────────────────────────

GATE_DB = {
    "os": {
        "name": "Operating Systems",
        "keywords": ["operating system", "os ", " os,", "process scheduling", "deadlock", "semaphore", "paging"],
        "high_frequency_topics": [
            {"topic": "CPU Scheduling (FCFS, SJF, RR, Priority)", "gate_frequency": "Very High", "tip": "Always calculate turnaround time, waiting time, and CPU utilization"},
            {"topic": "Deadlock — Detection, Avoidance (Banker's Algorithm)", "gate_frequency": "Very High", "tip": "Identify safe sequences, resource allocation graphs"},
            {"topic": "Page Replacement (LRU, FIFO, Optimal)", "gate_frequency": "Very High", "tip": "Count page faults for a given reference string"},
            {"topic": "Memory Management — Paging, Segmentation", "gate_frequency": "High", "tip": "Calculate effective access time, page table entries"},
            {"topic": "Semaphores & Synchronization (Producer-Consumer, Reader-Writer)", "gate_frequency": "High", "tip": "Critical section problems, race conditions"},
            {"topic": "Virtual Memory & Thrashing", "gate_frequency": "Medium", "tip": "Working set model, demand paging"},
            {"topic": "File System (Inode, FAT, Directory)", "gate_frequency": "Medium", "tip": "Disk block allocation, inode calculations"},
            {"topic": "Disk Scheduling (SSTF, SCAN, C-SCAN)", "gate_frequency": "Medium", "tip": "Seek time calculations"},
        ],
        "gate_sample_patterns": [
            "Given processes with burst times, calculate average waiting time using Round Robin with quantum=2",
            "For a system with N resources and M processes, determine if the system is in a safe state",
            "Given reference string and frame count, find number of page faults using LRU/FIFO/Optimal",
            "A page table has X entries, page size is Y bytes. Find physical address for given virtual address",
            "In a system with binary semaphores, identify which code snippet causes deadlock",
        ]
    },
    "dbms": {
        "name": "Database Management Systems",
        "keywords": ["database", "dbms", "rdbms", "sql", "normalization", "er diagram", "relational"],
        "high_frequency_topics": [
            {"topic": "Normalization (1NF, 2NF, 3NF, BCNF)", "gate_frequency": "Very High", "tip": "Given a relation and FDs, find the highest normal form"},
            {"topic": "SQL Queries (JOIN, GROUP BY, HAVING, Subqueries)", "gate_frequency": "Very High", "tip": "Write/trace complex SQL with aggregates and joins"},
            {"topic": "Relational Algebra & Calculus", "gate_frequency": "High", "tip": "Convert SQL to relational algebra and vice versa"},
            {"topic": "Indexing (B-Tree, B+ Tree, Hashing)", "gate_frequency": "High", "tip": "Calculate number of disk accesses, tree height"},
            {"topic": "Transaction Management (ACID, Serializability)", "gate_frequency": "High", "tip": "Check if a schedule is conflict/view serializable"},
            {"topic": "ER Diagram to Relational Schema", "gate_frequency": "Medium", "tip": "Identify primary keys, foreign keys from ER diagram"},
            {"topic": "Functional Dependencies & Closure", "gate_frequency": "Very High", "tip": "Find attribute closure, candidate keys, minimal cover"},
            {"topic": "Query Processing & Optimization", "gate_frequency": "Medium", "tip": "Cost estimation for different join strategies"},
        ],
        "gate_sample_patterns": [
            "Given relation R(A,B,C,D) with FDs, find all candidate keys",
            "Given relation with FDs, decompose to BCNF and check for lossless join",
            "Write SQL query to find employees earning more than average salary in their department",
            "Given a schedule of transactions, check conflict serializability using precedence graph",
            "A B+ tree of order m has N keys. Find minimum/maximum number of leaf nodes",
        ]
    },
    "cn": {
        "name": "Computer Networks",
        "keywords": ["computer network", "networking", "cn ", "tcp", "ip", "osi", "protocol", "routing"],
        "high_frequency_topics": [
            {"topic": "TCP/IP Protocol Suite & OSI Model", "gate_frequency": "Very High", "tip": "Layer functions, protocol mapping, PDU names"},
            {"topic": "Routing Algorithms (Dijkstra, Bellman-Ford, Distance Vector)", "gate_frequency": "Very High", "tip": "Compute shortest paths, detect routing loops"},
            {"topic": "Sliding Window Protocol & Error Control", "gate_frequency": "Very High", "tip": "Calculate throughput, efficiency, window size"},
            {"topic": "IP Addressing — Subnetting, CIDR, VLSM", "gate_frequency": "High", "tip": "Find network address, broadcast, number of hosts"},
            {"topic": "TCP — 3-way handshake, Congestion Control (AIMD)", "gate_frequency": "High", "tip": "RTT calculations, congestion window evolution"},
            {"topic": "Application Layer (DNS, HTTP, FTP, SMTP)", "gate_frequency": "Medium", "tip": "How DNS resolution works, HTTP methods"},
            {"topic": "MAC Protocols (CSMA/CD, CSMA/CA, Aloha)", "gate_frequency": "High", "tip": "Throughput calculations for Aloha variants"},
            {"topic": "Error Detection (CRC, Checksum, Hamming Code)", "gate_frequency": "High", "tip": "Compute CRC remainder, detect/correct errors"},
        ],
        "gate_sample_patterns": [
            "Given a network with N nodes and link costs, find shortest path using Dijkstra's algorithm",
            "A Go-Back-N protocol uses window size W. Find the efficiency for given propagation delay",
            "Subnet a given IP address into N subnets with specified host counts using VLSM",
            "TCP connection starts with cwnd=1 MSS. Trace congestion window after slow start and congestion",
            "A CRC generator polynomial is given. Find the CRC for a given message bit string",
        ]
    },
    "dsa": {
        "name": "Data Structures & Algorithms",
        "keywords": ["data structure", "algorithm", "dsa", "sorting", "tree", "graph", "linked list", "stack", "queue", "heap"],
        "high_frequency_topics": [
            {"topic": "Sorting Algorithms (QuickSort, MergeSort, HeapSort)", "gate_frequency": "Very High", "tip": "Time/space complexity, worst/best/average cases, comparisons"},
            {"topic": "Trees — BST, AVL, Red-Black, Heap", "gate_frequency": "Very High", "tip": "Insert/delete operations, height calculation, rotations"},
            {"topic": "Graph Algorithms (BFS, DFS, Dijkstra, Kruskal, Prim)", "gate_frequency": "Very High", "tip": "Trace algorithms, find MST cost, detect cycles"},
            {"topic": "Dynamic Programming (LCS, LIS, Knapsack, Matrix Chain)", "gate_frequency": "Very High", "tip": "Write recurrence, fill DP table, find optimal solution"},
            {"topic": "Hashing (Collision Handling, Load Factor)", "gate_frequency": "High", "tip": "Open addressing vs chaining, expected search time"},
            {"topic": "Time & Space Complexity (Big-O, Recurrences)", "gate_frequency": "Very High", "tip": "Solve recurrences using Master Theorem"},
            {"topic": "Linked Lists, Stacks, Queues", "gate_frequency": "Medium", "tip": "Detect cycles, reverse, infix-postfix conversion"},
            {"topic": "Greedy Algorithms (Activity Selection, Huffman)", "gate_frequency": "High", "tip": "Prove greedy choice, build Huffman tree"},
        ],
        "gate_sample_patterns": [
            "An AVL tree has N nodes. What is the minimum/maximum height? After insertion, identify rotations needed",
            "Given a graph G, find the minimum spanning tree cost using Kruskal's algorithm",
            "Solve the recurrence T(n) = 2T(n/2) + n using Master Theorem. What is the time complexity?",
            "Given sequences X and Y, find the length of Longest Common Subsequence",
            "QuickSort is applied on an array. How many comparisons in the worst case?",
        ]
    },
    "toc": {
        "name": "Theory of Computation",
        "keywords": ["theory of computation", "toc", "automata", "dfa", "nfa", "grammar", "turing", "cfg", "pda", "regular language"],
        "high_frequency_topics": [
            {"topic": "DFA & NFA — Construction, Equivalence, Minimization", "gate_frequency": "Very High", "tip": "Build DFA/NFA for given language, convert NFA to DFA, minimize DFA"},
            {"topic": "Regular Expressions & Regular Languages", "gate_frequency": "Very High", "tip": "Convert between RE, DFA, NFA. Use pumping lemma to prove non-regularity"},
            {"topic": "Context-Free Grammars (CFG) & PDAs", "gate_frequency": "Very High", "tip": "Design CFG for a language, convert to CNF, draw PDA"},
            {"topic": "Pushdown Automata (PDA)", "gate_frequency": "High", "tip": "Design PDA for CFL, trace acceptance"},
            {"topic": "Turing Machines", "gate_frequency": "High", "tip": "Design TM for language, understand decidability"},
            {"topic": "Decidability & Undecidability", "gate_frequency": "High", "tip": "Halting problem, Rice's theorem, reductions"},
            {"topic": "Pumping Lemma (Regular & CFL)", "gate_frequency": "High", "tip": "Use to prove a language is not regular/CFL"},
            {"topic": "Closure Properties of Language Classes", "gate_frequency": "Medium", "tip": "Is the class closed under union, concatenation, complement?"},
        ],
        "gate_sample_patterns": [
            "Construct a minimum state DFA that accepts strings over {0,1} ending in '101'",
            "Using pumping lemma, prove that L = {a^n b^n | n>=1} is not regular",
            "Design a PDA that accepts L = {a^n b^n c^n | n>=0}. Is this language context-free?",
            "Which of the following problems is decidable? (Halting, Emptiness of CFL, Equivalence of CFGs...)",
            "Convert the given CFG to Chomsky Normal Form (CNF)",
        ]
    },
    "cd": {
        "name": "Compiler Design",
        "keywords": ["compiler", "compiler design", "cd", "lexical", "parsing", "grammar", "token", "syntax"],
        "high_frequency_topics": [
            {"topic": "Lexical Analysis (Regular Expressions, DFA for tokens)", "gate_frequency": "High", "tip": "Identify tokens, build DFA for scanner"},
            {"topic": "Parsing — LL(1), LR(0), SLR, LALR, CLR", "gate_frequency": "Very High", "tip": "Construct parse tables, identify shift-reduce conflicts"},
            {"topic": "FIRST and FOLLOW Sets", "gate_frequency": "Very High", "tip": "Compute FIRST/FOLLOW for given grammar"},
            {"topic": "Syntax-Directed Translation (SDT)", "gate_frequency": "High", "tip": "Annotate parse tree, evaluate attribute grammar"},
            {"topic": "Intermediate Code Generation (3-address code, TAC)", "gate_frequency": "High", "tip": "Generate TAC for expressions, if-else, loops"},
            {"topic": "Code Optimization (Loop invariant, Dead code, CSE)", "gate_frequency": "Medium", "tip": "Identify and apply optimizations"},
            {"topic": "Code Generation & Register Allocation", "gate_frequency": "Medium", "tip": "Generate assembly, allocate registers using graph coloring"},
        ],
        "gate_sample_patterns": [
            "Compute FIRST and FOLLOW sets for the given grammar G",
            "Construct the LR(0) items for grammar G and build the SLR(1) parse table",
            "Generate three-address code for the expression: a = b * c + b * d",
            "Identify the type of grammar: regular, CFL, CSL, or unrestricted",
            "Given a grammar, check if it is LL(1). If not, eliminate left recursion",
        ]
    },
    "coa": {
        "name": "Computer Organization & Architecture",
        "keywords": ["computer organization", "coa", "architecture", "pipeline", "cache", "cpu", "instruction", "memory hierarchy"],
        "high_frequency_topics": [
            {"topic": "Pipelining — Hazards, Speedup, Efficiency", "gate_frequency": "Very High", "tip": "Calculate pipeline speedup, CPI with/without stalls"},
            {"topic": "Cache Memory (Mapping, Hit/Miss Ratio, AMAT)", "gate_frequency": "Very High", "tip": "Direct/set-associative/fully-associative mapping, AMAT formula"},
            {"topic": "Number Systems (2's Complement, IEEE 754)", "gate_frequency": "High", "tip": "Convert float to IEEE 754, perform arithmetic"},
            {"topic": "Memory Hierarchy — Main Memory, Virtual Memory", "gate_frequency": "High", "tip": "Calculate effective access time, page table calculations"},
            {"topic": "Instruction Set Architecture (RISC vs CISC)", "gate_frequency": "Medium", "tip": "Addressing modes, instruction formats"},
            {"topic": "DMA, Interrupts, I/O Organization", "gate_frequency": "Medium", "tip": "DMA transfer time, interrupt handling"},
            {"topic": "Booth's Algorithm, Array Multiplier", "gate_frequency": "Medium", "tip": "Multiply numbers using Booth's algorithm"},
        ],
        "gate_sample_patterns": [
            "A 5-stage pipeline has given stage delays. Find the maximum clock frequency and speedup over non-pipelined",
            "A cache has block size B, associativity A. Given reference string, find hit rate",
            "Calculate AMAT given cache access time, miss penalty, and miss rate",
            "Convert the decimal number -35.625 to IEEE 754 single precision format",
            "A DMA transfer occurs for N blocks of size B each. Calculate total transfer time",
        ]
    },
    "dm": {
        "name": "Discrete Mathematics",
        "keywords": ["discrete", "discrete math", "dm ", "combinatorics", "graph theory", "set theory", "logic", "proposition", "relation"],
        "high_frequency_topics": [
            {"topic": "Graph Theory (Euler, Hamilton, Coloring, Planarity)", "gate_frequency": "Very High", "tip": "Identify Eulerian/Hamiltonian graphs, chromatic number"},
            {"topic": "Combinatorics (Permutations, Combinations, Inclusion-Exclusion)", "gate_frequency": "Very High", "tip": "Count arrangements with/without repetition, solve inclusion-exclusion problems"},
            {"topic": "Mathematical Logic (Propositional, First-Order)", "gate_frequency": "High", "tip": "Truth tables, CNF/DNF, tautology, predicate logic"},
            {"topic": "Relations (Partial Orders, Equivalence, Hasse Diagram)", "gate_frequency": "High", "tip": "Properties of relations, Hasse diagrams, lattices"},
            {"topic": "Set Theory (Power Set, Cartesian Product)", "gate_frequency": "High", "tip": "Cardinality, set identities, Venn diagrams"},
            {"topic": "Generating Functions & Recurrence Relations", "gate_frequency": "Medium", "tip": "Solve recurrences with characteristic equations"},
            {"topic": "Group Theory (Semigroup, Monoid, Group)", "gate_frequency": "Medium", "tip": "Verify group axioms, subgroups, cyclic groups"},
        ],
        "gate_sample_patterns": [
            "How many non-isomorphic simple graphs exist with N vertices?",
            "In how many ways can N people be seated in a row such that A and B are always together?",
            "Find the chromatic polynomial/number of a given graph",
            "Which of the following first-order formulas is valid (tautology)?",
            "Given the recurrence T(n) = T(n-1) + n, solve for T(n)",
        ]
    }
}


# ─── Utility Functions ────────────────────────────────────────────────────────

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought", "used",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "up", "about",
    "into", "through", "during", "before", "after", "above", "below", "between",
    "each", "or", "and", "but", "if", "or", "because", "as", "until", "while",
    "that", "this", "these", "those", "it", "its", "what", "which", "who",
    "also", "such", "no", "so", "both", "more", "other", "same", "than",
    "then", "all", "any", "their", "there", "where", "when", "how", "not"
}


def tokenize(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = text.split()
    return [w for w in words if w not in STOP_WORDS and len(w) > 2]


def similarity(text1, text2):
    set1 = set(tokenize(text1))
    set2 = set(tokenize(text2))
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def sequence_similarity(text1, text2):
    return difflib.SequenceMatcher(None, text1.lower().strip(), text2.lower().strip()).ratio()


# ─── PDF Text Extraction ──────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path):
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t and t.strip():
                    pages.append(t.strip())
    except Exception as e:
        raise RuntimeError(f"Cannot read PDF '{os.path.basename(pdf_path)}': {e}")
    return "\n".join(pages)


def extract_pages_from_pdf(pdf_path):
    """Return list of (page_index, page_text) tuples."""
    result = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text()
                result.append((i, t.strip() if t else ""))
    except Exception as e:
        raise RuntimeError(f"Cannot read PDF '{os.path.basename(pdf_path)}': {e}")
    return result


# ─── Merged PDF: detect year sections ────────────────────────────────────────

def detect_year_on_page(text):
    """Return the most frequently mentioned year (4-digit format) on this page, or None."""
    # 1. 4-digit years: 2015 to 2029
    fours = re.findall(r'\b(201[5-9]|202[0-9])\b', text)
    if fours:
        return collections.Counter(fours).most_common(1)[0][0]

    # 2. 2-digit years preceded by standard separator or special unicode symbol: '23, ’24, 19, -18
    twos = re.findall(r"[’'‘`\-]\s*(1[5-9]|2[0-9])\b", text)
    if twos:
        best_two = collections.Counter(twos).most_common(1)[0][0]
        return f"20{best_two}"

    return None


def split_merged_pdf_by_year(pdf_path):
    """
    Try to split a single merged PDF into year-based sections.
    Returns list of {"year": str, "text": str, "page_count": int}
    If unable to detect multiple years, returns a single section.
    """
    pages = extract_pages_from_pdf(pdf_path)
    if not pages:
        return []

    # Assign a year to each page
    page_year_assignments = []
    current_year = None

    for idx, text in pages:
        detected = detect_year_on_page(text)
        if detected:
            current_year = detected
        page_year_assignments.append((idx, text, current_year))

    # If no year detected anywhere, fall back to page-based halving
    # (e.g. assume first half = year A, second half = year B — not reliable, skip)
    all_years = [y for _, _, y in page_year_assignments if y]
    if not all_years:
        # No years detected — treat entire PDF as one paper
        full_text = "\n".join(t for _, t, _ in page_year_assignments)
        return [{"year": "merged", "text": full_text, "page_count": len(pages)}]

    # Group consecutive pages by detected year
    groups = {}
    group_order = []
    for idx, text, year in page_year_assignments:
        y = year or "unknown"
        if y not in groups:
            groups[y] = []
            group_order.append(y)
        groups[y].append(text)

    sections = []
    for y in group_order:
        full_text = "\n".join(groups[y])
        if full_text.strip():
            sections.append({
                "year": y,
                "text": full_text,
                "page_count": len(groups[y])
            })

    return sections


# ─── Question Extraction ──────────────────────────────────────────────────────

# Modified patterns: only split on major question headings and top-level subparts (a-h)
# Avoid splitting on (i), (ii), (iii) or (1), (2), (3) inside a parent question
QUESTION_START_PATTERNS = [
    re.compile(r'(?:^|\n)\s*Q\.?\s*\d+[\.\)\s]', re.MULTILINE),
    re.compile(r'(?:^|\n)\s*\d{1,2}\.\s+[A-Z]', re.MULTILINE),
    re.compile(r'(?:^|\n)\s*[\(\[]\s*([a-hA-H])\s*[\)\]]', re.MULTILINE), # Only letters a-h representing subparts
    re.compile(r'(?:^|\n)\s*[Qq]uestion(?:\s+[Nn]o\.?)?\s*\d+', re.MULTILINE),
    re.compile(r'(?:^|\n)\s*[Pp]art\s*[\(\[]?\s*[a-zA-Z]', re.MULTILINE),
]

def is_generic_instruction(text):
    """Return True if the text matches generic exam metadata/instructions instead of a real question."""
    t = text.lower()
    # Very short strings that contain instruction-like keywords
    if len(text) < 150:
        keywords = [
            "compulsory", "carry marks", "suitable data", "neat sketch", "draw a diagram",
            "candidate should", "attempt any", "answer any", "choice", "serial number",
            "maximum marks", "time allowed", "course code", "all questions", "marks as indicated",
            "wherever necessary", "parts of the same question", "figures to the right", "illustrate with"
        ]
        if any(kw in t for kw in keywords):
            return True
    
    # Metadata headers
    metadata_headers = ["semester b.tech", "semester b.e", "examination", "branch", "subject code", "duration"]
    if any(h in t for h in metadata_headers):
        return True
        
    return False

def extract_questions(text):
    markers = []
    for pat in QUESTION_START_PATTERNS:
        for m in pat.finditer(text):
            markers.append(m.start())
    markers = sorted(set(markers))

    questions = []
    if len(markers) >= 2:
        for i, start in enumerate(markers):
            end = markers[i + 1] if i + 1 < len(markers) else len(text)
            chunk = re.sub(r'\s+', ' ', text[start:end]).strip()
            # Length filter: must be reasonably sized, and not a generic instruction
            if 20 <= len(chunk) <= 6000:  # raised from 2500 — allow full long questions
                if not is_generic_instruction(chunk):
                    questions.append(chunk)

    # Fallback: extract sentences ending in ?
    if len(questions) < 3:
        found = re.findall(r'[A-Z][^.!?]{15,800}\?', text, re.MULTILINE)  # raised cap: 250→800
        for q in found:
            q = re.sub(r'\s+', ' ', q).strip()
            if q not in questions and not is_generic_instruction(q):
                questions.append(q)

    # Deduplicate
    seen = []
    unique = []
    for q in questions:
        # Pre-check similarity to avoid slow SequenceMatcher on different strings
        if not any(similarity(q, s) >= 0.40 and sequence_similarity(q, s) > 0.9 for s in seen):
            seen.append(q)
            unique.append(q)
    return unique


# ─── Topic Detection ──────────────────────────────────────────────────────────

TOPIC_KEYWORDS = {
    "Normalization":            ["normalization", "1nf", "2nf", "3nf", "bcnf", "normal form", "decomposition"],
    "SQL":                      ["sql", "select", "join", "inner join", "outer join", "group by", "having", "subquery"],
    "Indexing":                 ["index", "b-tree", "b+ tree", "b tree", "hashing", "hash table", "indexing"],
    "Transactions & ACID":      ["transaction", "acid", "atomicity", "consistency", "isolation", "durability", "commit", "rollback"],
    "ER Diagram":               ["er diagram", "entity relationship", "entity-relationship", "er model", "erd"],
    "Relational Algebra":       ["relational algebra", "relational calculus", "projection", "selection", "cartesian product"],
    "Functional Dependencies":  ["functional dependency", "fd", "closure", "candidate key", "minimal cover", "armstrong"],
    "CPU Scheduling":           ["scheduling", "fcfs", "sjf", "round robin", "priority scheduling", "turnaround time", "waiting time", "cpu burst"],
    "Deadlock":                 ["deadlock", "banker", "safe state", "resource allocation", "circular wait", "starvation"],
    "Page Replacement":         ["page replacement", "lru", "fifo", "optimal page", "page fault", "thrashing", "belady"],
    "Memory Management":        ["memory management", "paging", "segmentation", "virtual memory", "page table", "tlb", "address translation"],
    "Semaphores & Sync":        ["semaphore", "mutex", "synchronization", "critical section", "producer consumer", "race condition", "monitor"],
    "File Systems":             ["file system", "inode", "fat", "directory", "disk allocation", "file allocation"],
    "Sorting":                  ["sorting", "quicksort", "mergesort", "heapsort", "bubble sort", "insertion sort", "selection sort", "radix sort"],
    "Trees":                    ["binary tree", "bst", "avl tree", "red black", "b-tree", "heap", "tree traversal", "inorder", "preorder", "postorder"],
    "Graph Algorithms":         ["graph", "bfs", "dfs", "shortest path", "dijkstra", "bellman ford", "kruskal", "prim", "topological", "mst"],
    "Dynamic Programming":      ["dynamic programming", "dp ", "memoization", "lcs", "lis", "knapsack", "matrix chain", "coin change"],
    "Linked Lists":             ["linked list", "singly linked", "doubly linked", "circular linked"],
    "Hashing":                  ["hashing", "hash function", "collision", "chaining", "open addressing", "load factor"],
    "Complexity":               ["time complexity", "space complexity", "big o", "asymptotic", "recurrence", "master theorem"],
    "Greedy Algorithms":        ["greedy", "activity selection", "huffman", "fractional knapsack"],
    "TCP/IP & OSI":             ["tcp", "udp", "ip", "osi model", "layer", "protocol", "ethernet", "arp", "icmp"],
    "Routing":                  ["routing", "dijkstra", "bellman ford", "distance vector", "link state", "ospf", "bgp", "rip"],
    "Error Detection":          ["crc", "checksum", "hamming code", "error detection", "error correction", "parity"],
    "Subnetting":               ["subnetting", "subnet mask", "cidr", "vlsm", "ip address", "network address"],
    "Sliding Window":           ["sliding window", "go back n", "selective repeat", "flow control", "congestion control"],
    "DFA/NFA":                  ["dfa", "nfa", "finite automata", "deterministic", "non-deterministic", "state machine"],
    "Regular Expressions":      ["regular expression", "regular language", "kleene star", "pumping lemma"],
    "CFG & PDA":                ["cfg", "context free grammar", "pda", "pushdown automata", "parse tree", "ambiguous grammar"],
    "Turing Machine":           ["turing machine", "decidable", "undecidable", "halting problem", "recursive"],
    "Parsing":                  ["parsing", "ll(1)", "lr(0)", "slr", "lalr", "clr", "parse table", "shift reduce"],
    "FIRST/FOLLOW":             ["first set", "follow set", "first and follow", "nullable"],
    "Lexical Analysis":         ["lexical analysis", "lexer", "scanner", "token", "lexeme"],
    "Code Generation":          ["code generation", "three address code", "intermediate code", "tac"],
    "Pipelining":               ["pipeline", "pipelining", "hazard", "data hazard", "control hazard", "stall", "forwarding"],
    "Cache Memory":             ["cache", "hit ratio", "miss ratio", "amat", "direct mapped", "set associative"],
    "Number Systems":           ["2's complement", "ieee 754", "floating point", "binary", "hexadecimal"],
    "OOP Concepts":             ["oops", "oop", "object oriented", "class", "object", "inheritance", "polymorphism", "encapsulation", "abstraction"],
    "Combinatorics":            ["combinatorics", "permutation", "combination", "counting", "inclusion exclusion", "pigeonhole"],
    "Graph Theory":             ["euler", "hamilton", "chromatic number", "planar graph", "spanning tree"],
    "Logic":                    ["propositional logic", "predicate logic", "first order logic", "tautology", "satisfiable", "cnf", "dnf"],
}


def detect_topics(text):
    text_lower = text.lower()
    found = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        count = sum(len(re.findall(r'\b' + re.escape(kw) + r'\b', text_lower)) for kw in keywords)
        if count > 0:
            found[topic] = count
    return found


# ─── GATE Detection ───────────────────────────────────────────────────────────

def detect_gate_subject(subject_name):
    name_lower = subject_name.lower()
    for key, data in GATE_DB.items():
        for kw in data["keywords"]:
            if kw.strip() in name_lower:
                return key
        if key in name_lower or any(word in name_lower for word in data["name"].lower().split() if len(word) > 3):
            return key
    return None


# ─── Find Repeating Questions ─────────────────────────────────────────────────

def find_repeating_questions(papers):
    """
    papers: list of {"filename": str, "year": str, "questions": [str, ...]}
    Returns repeating question groups sorted by count descending.
    """
    all_items = []
    for paper in papers:
        for q in paper["questions"]:
            all_items.append({"q": q, "filename": paper["filename"], "year": paper.get("year", "?")})

    groups = []
    used = set()

    for i, item in enumerate(all_items):
        if i in used:
            continue
        group = {
            "question": item["q"],
            "appearances": [{"filename": item["filename"], "year": item["year"]}],
        }
        for j, other in enumerate(all_items):
            if i == j or j in used:
                continue
            if item["filename"] == other["filename"]:
                continue
            sim = similarity(item["q"], other["q"])
            if sim >= 0.55 or (sim >= 0.30 and sequence_similarity(item["q"], other["q"]) >= 0.70):
                already = any(a["filename"] == other["filename"] for a in group["appearances"])
                if not already:
                    group["appearances"].append({"filename": other["filename"], "year": other["year"]})
                    used.add(j)

        if len(group["appearances"]) >= 2:
            used.add(i)
            groups.append(group)

    groups.sort(key=lambda g: len(g["appearances"]), reverse=True)
    return groups


# ─── Main Analysis ────────────────────────────────────────────────────────────

def analyse(config):
    pdf_paths = config["pdfs"]
    subject_name = config.get("subject", "Unknown Subject")

    if not pdf_paths:
        raise ValueError("No PDF files provided")

    papers = []
    all_combined_text = ""
    is_merged_mode = False

    # ── Handle single merged PDF ──────────────────────────────────────────────
    if len(pdf_paths) == 1:
        path = pdf_paths[0]
        filename = os.path.basename(path)
        try:
            sections = split_merged_pdf_by_year(path)
        except RuntimeError as e:
            return {"success": False, "error": str(e)}

        if len(sections) >= 2:
            is_merged_mode = True
            for sec in sections:
                q = extract_questions(sec["text"])
                all_combined_text += "\n" + sec["text"]
                papers.append({
                    "filename": f"{filename} [{sec['year']}]",
                    "year": sec["year"],
                    "text": sec["text"],
                    "questions": q,
                    "question_count": len(q),
                })
        else:
            # Single paper
            try:
                text = extract_text_from_pdf(path)
                q = extract_questions(text)
                all_combined_text = text
                papers.append({
                    "filename": filename,
                    "year": "?",
                    "text": text,
                    "questions": q,
                    "question_count": len(q),
                })
            except RuntimeError as e:
                return {"success": False, "error": str(e)}

    # ── Handle multiple separate PDFs ─────────────────────────────────────────
    else:
        for path in pdf_paths:
            filename = os.path.basename(path)
            year_match = re.search(r'20[0-9]{2}', filename)
            year = year_match.group(0) if year_match else "?"
            try:
                text = extract_text_from_pdf(path)
                q = extract_questions(text)
                all_combined_text += "\n" + text
                papers.append({
                    "filename": filename,
                    "year": year,
                    "text": text,
                    "questions": q,
                    "question_count": len(q),
                })
            except RuntimeError as e:
                papers.append({"filename": filename, "year": year, "error": str(e), "questions": [], "question_count": 0})

    # ── Topic analysis ────────────────────────────────────────────────────────
    topic_counts = detect_topics(all_combined_text)
    sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)
    max_count = sorted_topics[0][1] if sorted_topics else 1

    top_topics = []
    for t, c in sorted_topics[:15]:
        ratio = c / max_count
        if ratio >= 0.75:
            band, band_color = "Very High", "#22c55e"
        elif ratio >= 0.50:
            band, band_color = "High", "#3b82f6"
        elif ratio >= 0.25:
            band, band_color = "Medium", "#f59e0b"
        else:
            band, band_color = "Low", "#64748b"
        top_topics.append({"topic": t, "count": c, "band": band, "band_color": band_color})

    # ── Repeating questions ───────────────────────────────────────────────────
    valid_papers = [p for p in papers if "error" not in p]
    repeating_groups = find_repeating_questions([
        {"filename": p["filename"], "year": p["year"], "questions": p["questions"]}
        for p in valid_papers
    ])

    repeating_output = []
    for g in repeating_groups[:50]:  # increased from 25 → 50
        years = sorted(set(a["year"] for a in g["appearances"] if a["year"] not in ("?", "merged", "unknown")))
        repeating_output.append({
            "question": g["question"],  # full text — truncation removed
            "count": len(g["appearances"]),
            "years": years,
            "filenames": list(set(a["filename"] for a in g["appearances"])),
        })

    # ── GATE analysis ─────────────────────────────────────────────────────────
    gate_key = detect_gate_subject(subject_name)
    if gate_key and gate_key in GATE_DB:
        gd = GATE_DB[gate_key]
        gate_analysis = {
            "detected": True,
            "gate_subject": gd["name"],
            "high_frequency_topics": gd["high_frequency_topics"],
            "gate_sample_patterns": gd["gate_sample_patterns"],
            "message": f"'{subject_name}' matches GATE subject: {gd['name']}"
        }
    else:
        gate_analysis = {
            "detected": False,
            "message": f"'{subject_name}' is not directly mapped to a GATE subject."
        }

    total_questions = sum(p.get("question_count", 0) for p in valid_papers)

    return {
        "success": True,
        "subject": subject_name,
        "isMergedMode": is_merged_mode,
        "summary": {
            "totalPapers": len(pdf_paths),
            "sectionsDetected": len(papers),
            "papersProcessed": len(valid_papers),
            "totalQuestionsFound": total_questions,
            "repeatingQuestionsFound": len(repeating_output),
            "topicsDetected": len(top_topics),
        },
        "papers": [
            {"filename": p["filename"], "year": p["year"], "questionsFound": p.get("question_count", 0)}
            for p in papers
        ],
        "repeatingQuestions": repeating_output,
        "topicAnalysis": top_topics,
        "highProbabilityTopics": [t for t in top_topics if t["band"] in ("Very High", "High")],
        "gateAnalysis": gate_analysis,
    }


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(json.dumps({"success": False, "error": "Usage: python analyse.py <config.json>"}))
        sys.exit(1)

    config_path = sys.argv[1]
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        result = analyse(config)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)
