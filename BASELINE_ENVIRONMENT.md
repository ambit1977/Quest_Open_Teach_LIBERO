# Baseline environment before Open Teach

Recorded on 2026-08-19 before changing the Open Teach checkout.

- macOS 26.3.1, arm64 (Apple Silicon M5)
- Homebrew Python outside the project: 3.14.5
- Existing LIBERO Python: 3.10.20
- LIBERO-plus commit: `4976dc30028e805ff8094b55501d532c48fec182`
- LIBERO-plus source: `../コンテスト/PARC2026/upstream/LIBERO-plus`
- robosuite: 1.4.0
- MuJoCo: 3.7.0
- NumPy: 1.26.4
- PyTorch: 2.13.0
- Open Teach upstream commit: `32a7d44b33953066ff27312a7b2b4c294f4f52c5`

The existing PARC2026 virtual environment was not modified. Open Teach's
macOS-only additions (`pyzmq`, `blosc`) are installed in this checkout's
`.venv` and the launcher references the existing LIBERO environment read-only.
