# Project Explanation: DGRE Water Resources Assistant

## What is this project?

This is a tool that helps you find and understand water-related data from two official Tunisian publications covering the 2022–2023 period:

1. **Annuaire hydraulique (Hydrological Yearbook)** – 145 pages about river flows, dam levels, and water measurements
2. **Annuaire pluviométrique (Rainfall Yearbook)** – 242 pages about daily and monthly rainfall amounts

The system lets you ask questions in plain language and get answers backed by the actual documents, with references to where the information comes from.

---

## The RAG Pipeline (How it works)

RAG stands for **Retrieval-Augmented Generation**. Think of it as a two-step process:

### Step 1 – Retrieve the relevant information
- The system "reads" both PDF documents and extracts text, tables, and structured data (like daily rainfall values at specific stations)
- It creates an index that makes it fast to find what you're looking for
- When you ask a question, the system searches this index to find the most relevant passages and data

### Step 2 – Generate a response
- Using the found information, the system creates a clear answer in natural language
- It also provides citations so you can verify the information by looking at the original document pages
- If the question requires calculations (e.g., "compare two stations"), the system performs those calculations using the extracted data

---

## How the files and data fit together

### The two source documents
- **Hydrological data**: River flow measurements (in cubic meters per second), dam levels, historical flood records
- **Rainfall data**: Daily and monthly rainfall amounts (in millimeters) at various stations across Tunisia

### The processing pipeline (behind the scenes)

1. **Ingestion** – The system reads each PDF page by page, extracts:
   - Text content
   - Tables containing measurement data
   - Identifies which station each measurement belongs to
   - Determines what type of measurement it is (rainfall, flow, etc.)

2. **Storage** – All extracted data is stored in a structured database (SQLite) with:
   - Metadata about each document and page
   - The extracted text and tables
   - Links between related data (e.g., which station a measurement belongs to)
   - Quality checks and validation status

3. **Indexing** – Two types of search indexes are created:
   - **Lexical index** (BM25): Finds pages by keyword matching, like a search engine
   - **Vector index**: Uses mathematical representations (embeddings) to find content semantically related to your question

4. **Query processing** – When you ask a question:
   - The system interprets what you're looking for (which station, what metric, what time period)
   - It searches both indexes to find relevant information
   - If needed, it performs calculations (totals, comparisons, etc.)
   - It generates a natural language answer with proper citations

5. **Response** – You get:
   - A clear answer in plain language
   - The numeric value (if applicable) with units
   - The time period covered
   - References to the source document and page
   - Notes about any limitations or missing data

---

## What you can do with it

### Simple lookups
- "What was the daily rainfall maximum at station Aïn Draham in 2022–2023?"
- "Show me the annual rainfall total for station Tunis."

### Comparisons
- "Compare the annual rainfall between stations Aïn Draham and Jendouba in 2022–2023."
- "Which station had the higher maximum daily flow in 2022–2023?"

### Series and summaries
- "Show me the monthly rainfall values for station Amdoun throughout 2022–2023."
- "How many rain-free days were recorded at station Sidi Salem?"

### Source verification
- Every answer includes references to the original document pages
- You can click through to view the actual PDF page from which the information was extracted

---

## Data coverage

The system covers the **2022–2023 hydrological year** (September 2022 through August 2023) for Tunisian water resources monitoring. Some key points:

- **Complete coverage** for published annual and monthly summaries
- **Daily data** may have gaps (some days marked as "missing" or "lacune")
- **Published totals** are available, but calculated sums may be blocked if the daily series is incomplete
- **Quality indicators** are shown, noting when data is limited or anomalous

---

## Getting started

1. Launch the application – you'll see two tabs: **Assistant** and **Sources**
2. In the **Assistant** tab, type a question in natural language
3. The system will find the relevant information and give you an answer with sources
4. Use the **Sources** tab to browse the PDF documents directly if you want to verify or explore

The system is designed to help you understand what the data says, while being clear about what's published, what's calculable, and what limitations exist in the original documents.