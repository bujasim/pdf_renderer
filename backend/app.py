import sys
from pathlib import Path

import webview


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    html_path = (base_dir / ".." / "web" / "index.html").resolve()

    if not html_path.exists():
        raise FileNotFoundError(f"Missing UI build output: {html_path}")

    initial_pdf = None
    if len(sys.argv) > 1:
        pdf_path = Path(sys.argv[1]).expanduser().resolve()
        if pdf_path.exists():
            initial_pdf = pdf_path.as_uri()

    url = html_path.as_uri()
    if initial_pdf:
        url = f"{url}?file={initial_pdf}"

    webview.create_window(
        "PDF Viewer",
        url=url,
        width=1200,
        height=800,
        min_size=(900, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
