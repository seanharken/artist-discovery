import json
import re
from pathlib import Path

TEMPLATE_PATH = "dashboard_template.html"
DATA_PATH = "dashboard_data.json"
OUTPUT_PATH = "dashboard.html"


def build():
    template = Path(TEMPLATE_PATH).read_text(encoding="utf-8")
    data = json.loads(Path(DATA_PATH).read_text(encoding="utf-8"))
    payload = json.dumps(data)

    pattern = re.compile(
        r'(<script type="application/json" id="pipeline-data">)(.*?)(</script>)',
        re.DOTALL,
    )
    new_html, count = pattern.subn(
        lambda m: m.group(1) + payload + m.group(3), template, count=1
    )
    if count == 0:
        raise RuntimeError(
            "Could not find the pipeline-data script tag in dashboard_template.html. "
            "Make sure it's the exact file you saved from the pasted HTML."
        )

    Path(OUTPUT_PATH).write_text(new_html, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} with {len(data.get('artists', []))} artists.")


if __name__ == "__main__":
    build()