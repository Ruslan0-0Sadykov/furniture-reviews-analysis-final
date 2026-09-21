from pathlib import Path


def test_outputs_do_not_contain_secrets():
    root=Path(__file__).resolve().parents[1]
    env=root/".env"
    if not env.exists(): return
    secrets=[]
    for line in env.read_text(encoding="utf-8",errors="ignore").splitlines():
        if "=" in line:
            key,value=line.split("=",1)
            if key.strip() in {"YANDEX_API_KEY","YANDEX_FOLDER_ID"} and len(value.strip())>=8: secrets.append(value.strip())
    for folder in [root/"outputs",root/"report",root/"datalens"]:
        for path in folder.rglob("*") if folder.exists() else []:
            if path.is_file() and path.suffix.lower() in {".txt",".md",".csv",".json"}:
                text=path.read_text(encoding="utf-8",errors="ignore")
                assert all(secret not in text for secret in secrets)

