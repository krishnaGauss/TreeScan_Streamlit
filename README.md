# Tree QR and PDF Generator

A Streamlit web app for generating QR code labels and enhanced PDF reports for tree inventory datasets.

Live app: [treescan.streamlit.app](https://treescan.streamlit.app)

---

## What it does

The app has two modes:

**QR Generation** -- Upload a CSV and provide a base URL. The app generates a branded QR code image for each tree row, encoding a URL of the form `<base_url>/<S_No_>.pdf`. All images are packaged into a downloadable ZIP.

**PDF Generation** -- Upload a CSV and a ZIP of per-tree PDFs. The app prepends a header, a data table (populated from the CSV row), and appends a footer to each PDF. The results are packaged into a downloadable ZIP.

### CSV format

The CSV must include the following columns:

| Column | Description |
|---|---|
| S_No_ | Serial number, used as the filename and URL key |
| Vernacular | Common name (English name extracted from parentheses if present) |
| Scientific | Scientific name |
| Family | Plant family |
| Remarks_ | Any remarks |
| Latitude | GPS latitude |
| Longitude | GPS longitude |
| Plant_Orig | Plant origin |

---

## Local installation

**Requirements:** Python 3.10 or later.

1. Clone the repository:

```bash
git clone https://github.com/krishnaGauss/TreeScan_Streamlit.git
cd TreeScan_Streamlit
```

2. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the app

```bash
streamlit run main.py
```

The app will open in your browser at `http://localhost:8501`.
