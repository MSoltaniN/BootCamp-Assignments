"""Absolute project paths so every module agrees on where data lives."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATASETS = ROOT / "datasets"
ARTIFACTS = ROOT / "artifacts"
WORK = ROOT / "work"
MODEL_DIR = ROOT / "resources" / "embedding_model"
DB_PATH = ROOT / "day3.sqlite"

CORPUS = DATASETS / "01_Corpus"
CORPUS_RAW = CORPUS / "raw"
MANIFEST = CORPUS / "manifest.csv"
EVAL = DATASETS / "02_Evaluation"
APP = DATASETS / "03_Application"
API = DATASETS / "04_API"
ROUTER = DATASETS / "05_Router"
ROBUST = DATASETS / "06_Robustness"
OBS = DATASETS / "07_Observability"
