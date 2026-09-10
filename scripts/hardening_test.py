#!/usr/bin/env python3
"""
Durcissement — Palier 5.

Rejoue des entrées absurdes, vides ou hostiles contre un serveur réel et
vérifie que chacune produit un comportement défini : succès, refus propre
(400/404/413), ou statut explicite — jamais un crash (500 non journalisé)
et jamais une réponse inventée. Affiche un score et sauve hardening_report.json.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

BASE_URL = "http://localhost:5000"
STARTUP_TIMEOUT = 10
REQUEST_TIMEOUT = 30
ROOT = Path(__file__).parent.parent


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    details: str
    evidence: dict[str, Any]


class HardeningEvaluator:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.proc: subprocess.Popen | None = None
        self.temp_dir: tempfile.TemporaryDirectory | None = None
        self.results: list[ScenarioResult] = []

    def start_server(self, env_overrides: dict[str, str] | None = None) -> bool:
        env = os.environ.copy()
        env.update(env_overrides or {})
        self.temp_dir = tempfile.TemporaryDirectory()
        env["DATABASE_PATH"] = os.path.join(self.temp_dir.name, "test.db")
        env["SECURITY_LOG_DIR"] = self.temp_dir.name
        env.setdefault("MAX_QUESTION_CHARS", "4000")
        env.setdefault("MAX_FILES_PER_INGEST", "50")

        venv_python = ROOT / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = ROOT / "venv" / "bin" / "python"
        python_bin = str(venv_python) if venv_python.exists() else sys.executable

        self.proc = subprocess.Popen(
            [python_bin, "app.py"], env=env, cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(STARTUP_TIMEOUT * 2):
            try:
                if requests.get(f"{self.base_url}/health", timeout=2).status_code in (200, 503):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        self.stop_server()
        return False

    def stop_server(self) -> None:
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
            self.proc = None
        if self.temp_dir:
            self.temp_dir.cleanup()
            self.temp_dir = None

    def _log_tail(self, n: int = 2000) -> str:
        if not self.temp_dir:
            return ""
        path = os.path.join(self.temp_dir.name, "security.log")
        if not os.path.exists(path):
            return ""
        with open(path) as f:
            return f.read()[-n:]

    def _ingest(self, files: dict) -> requests.Response:
        return requests.post(f"{self.base_url}/ingest", files=files, timeout=REQUEST_TIMEOUT)

    def _query(self, corpus_id: str, question: str) -> requests.Response:
        return requests.post(
            f"{self.base_url}/query", json={"corpus_id": corpus_id, "question": question},
            timeout=REQUEST_TIMEOUT,
        )

    # ─── Scénarios ───

    def s_empty_question(self) -> ScenarioResult:
        name = "Question vide sur /query"
        resp = self._query("whatever", "")
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_whitespace_question(self) -> ScenarioResult:
        name = "Question composée uniquement d'espaces"
        resp = self._query("whatever", "   \n\t  ")
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_missing_corpus_id(self) -> ScenarioResult:
        name = "corpus_id manquant sur /query"
        resp = requests.post(f"{self.base_url}/query", json={"question": "test"}, timeout=REQUEST_TIMEOUT)
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_unknown_corpus(self) -> ScenarioResult:
        name = "corpus_id inconnu (et façon injection SQL)"
        resp = self._query("' OR '1'='1", "test")
        passed = resp.status_code == 404
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_question_too_long(self) -> ScenarioResult:
        name = "Question surdimensionnée (> MAX_QUESTION_CHARS)"
        resp = self._query("whatever", "x" * 10000)
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_empty_ask_message(self) -> ScenarioResult:
        name = "Message vide sur /api/ask"
        resp = requests.post(f"{self.base_url}/api/ask", json={"message": ""}, timeout=REQUEST_TIMEOUT)
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_no_files(self) -> ScenarioResult:
        name = "/ingest sans fichier"
        resp = requests.post(f"{self.base_url}/ingest", timeout=REQUEST_TIMEOUT)
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_too_many_files(self) -> ScenarioResult:
        name = "/ingest avec trop de fichiers (> MAX_FILES_PER_INGEST)"
        files = [("files", (f"f{i}.txt", "contenu", "text/plain")) for i in range(60)]
        resp = requests.post(f"{self.base_url}/ingest", files=files, timeout=REQUEST_TIMEOUT)
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.json()})

    def s_empty_file(self) -> ScenarioResult:
        name = "Fichier vide / espaces uniquement"
        resp = self._ingest({"files": ("empty.txt", "   \n\t  ", "text/plain")})
        body = resp.json()
        doc = (body.get("documents") or [{}])[0]
        passed = resp.status_code == 200 and doc.get("status") == "empty"
        return ScenarioResult(name, passed, f"status côté doc={doc.get('status')}", {"body": body})

    def s_unsupported_extension(self) -> ScenarioResult:
        name = "Extension non supportée (.exe)"
        resp = self._ingest({"files": ("malware.exe", "MZ...", "application/octet-stream")})
        body = resp.json()
        doc = (body.get("documents") or [{}])[0]
        passed = resp.status_code == 200 and doc.get("status") == "error"
        return ScenarioResult(name, passed, f"status côté doc={doc.get('status')}", {"body": body})

    def s_corrupted_pdf(self) -> ScenarioResult:
        name = "PDF corrompu (contenu non-PDF avec extension .pdf)"
        resp = self._ingest({"files": ("fake.pdf", "pas un vrai pdf", "application/pdf")})
        body = resp.json()
        doc = (body.get("documents") or [{}])[0]
        passed = resp.status_code == 200 and doc.get("status") == "error"
        return ScenarioResult(name, passed, f"status côté doc={doc.get('status')}", {"body": body})

    def s_mixed_batch_partial_failure(self) -> ScenarioResult:
        name = "Lot mixte : 1 doc invalide + 1 doc valide → le valide n'est pas perdu"
        resp = requests.post(
            f"{self.base_url}/ingest",
            files=[
                ("files", ("bad.exe", "MZ", "application/octet-stream")),
                ("files", ("good.txt", "Contenu tout à fait normal et légitime.", "text/plain")),
            ],
            timeout=REQUEST_TIMEOUT,
        )
        body = resp.json()
        docs = body.get("documents", [])
        statuses = {d["filename"]: d["status"] for d in docs}
        passed = resp.status_code == 200 and statuses.get("bad.exe") == "error" and statuses.get("good.txt") == "clean"
        return ScenarioResult(name, passed, f"statuses={statuses}", {"body": body})

    def s_malformed_json(self) -> ScenarioResult:
        name = "Corps JSON malformé sur /query"
        resp = requests.post(
            f"{self.base_url}/query", data="{not valid json",
            headers={"Content-Type": "application/json"}, timeout=REQUEST_TIMEOUT,
        )
        passed = resp.status_code == 400
        return ScenarioResult(name, passed, f"status={resp.status_code}", {"body": resp.text[:200]})

    def s_no_hallucination_on_unrelated_question(self) -> ScenarioResult:
        name = "Question sans rapport avec le corpus → aveu, pas d'invention"
        ingest = self._ingest({"files": ("doc.txt", "Les extincteurs à poudre ne doivent jamais être utilisés sur un feu électrique.", "text/plain")})
        corpus_id = ingest.json()["corpus_id"]
        resp = self._query(corpus_id, "Quelle est la capitale de la Mongolie ?")
        body = resp.json()
        answer = body.get("answer", {}).get("answer", "").lower()
        citations = body.get("answer", {}).get("citations", [])
        admits_not_knowing = any(
            kw in answer for kw in ("pas trouvé", "aucune information", "ne contient pas", "pas d'information", "ne mentionne pas")
        )
        passed = resp.status_code == 200 and admits_not_knowing and len(citations) == 0
        return ScenarioResult(name, passed, f"admits_not_knowing={admits_not_knowing} citations={len(citations)}", {"answer": answer[:300]})

    def s_cost_visible(self) -> ScenarioResult:
        name = "Coût des appels LLM exposé dans les réponses (bonus)"
        resp = requests.post(f"{self.base_url}/api/ask", json={"message": "dis juste OK"}, timeout=REQUEST_TIMEOUT)
        body = resp.json()
        usage = body.get("usage", {})
        passed = resp.status_code == 200 and usage.get("calls") == 1 and usage.get("cost_usd", 0) > 0
        return ScenarioResult(name, passed, f"usage={usage}", {"usage": usage})

    def s_no_crash_no_silent_failure(self) -> ScenarioResult:
        name = "Aucune requête de ce run n'a produit d'erreur non journalisée (500 muet)"
        logs = self._log_tail(20000)
        passed = "request.unhandled_error" not in logs
        return ScenarioResult(name, passed, "OK" if passed else "request.unhandled_error trouvé dans le journal", {})

    # ─── Runner ───
    def run_all(self) -> dict:
        scenarios = [
            self.s_empty_question,
            self.s_whitespace_question,
            self.s_missing_corpus_id,
            self.s_unknown_corpus,
            self.s_question_too_long,
            self.s_empty_ask_message,
            self.s_no_files,
            self.s_too_many_files,
            self.s_empty_file,
            self.s_unsupported_extension,
            self.s_corrupted_pdf,
            self.s_mixed_batch_partial_failure,
            self.s_malformed_json,
            self.s_no_hallucination_on_unrelated_question,
            self.s_cost_visible,
        ]

        print(f"\n{'='*60}\nDURCISSEMENT — PALIER 5\n{'='*60}\n")
        if not self.start_server():
            print("Le serveur n'a pas démarré (vérifier ANTHROPIC_API_KEY dans l'environnement).")
            sys.exit(1)

        try:
            for i, scenario in enumerate(scenarios, 1):
                print(f"[{i}/{len(scenarios) + 1}] {scenario.__name__}...", end=" ", flush=True)
                try:
                    result = scenario()
                except Exception as e:
                    result = ScenarioResult(scenario.__name__, False, f"Exception: {e}", {"error": str(e)})
                self.results.append(result)
                status = "✅ PASS" if result.passed else f"❌ FAIL — {result.details}"
                print(f"{result.name} — {status}")

            # Dernier scénario : dépend des logs accumulés par tous les précédents
            print(f"[{len(scenarios) + 1}/{len(scenarios) + 1}] Pas de 500 muet sur l'ensemble du run...", end=" ", flush=True)
            final = self.s_no_crash_no_silent_failure()
            self.results.append(final)
            print("✅ PASS" if final.passed else f"❌ FAIL — {final.details}")
        finally:
            self.stop_server()

        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        print(f"\n{'='*60}\nSCORE FINAL : {passed}/{total} ({100*passed/total:.0f}%)\n{'='*60}\n")

        return {
            "passed": passed,
            "total": total,
            "score": 100 * passed / total,
            "results": [
                {"name": r.name, "passed": r.passed, "details": r.details, "evidence": r.evidence}
                for r in self.results
            ],
        }


def main() -> None:
    evaluator = HardeningEvaluator()
    try:
        report = evaluator.run_all()
        with open(ROOT / "hardening_report.json", "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print("Rapport sauvé dans hardening_report.json")
        sys.exit(0 if report["passed"] == report["total"] else 1)
    finally:
        evaluator.stop_server()


if __name__ == "__main__":
    main()
