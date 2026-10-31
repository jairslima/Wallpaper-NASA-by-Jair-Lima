"""Wallpaper NASA by Jair Lima, papel de parede astronômico diário para Windows."""

from __future__ import annotations

import argparse
import ctypes
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import winreg
import xml.etree.ElementTree as ET  # nosec B405 - feed validado em fetch_feed_items
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageOps, ImageTk, UnidentifiedImageError


APP_NAME = "Wallpaper NASA by Jair Lima"
API_URL = "https://api.nasa.gov/planetary/apod"
FEED_URL = "https://science.nasa.gov/feed/apod-basic/"
FEED_NS = {"apod": "https://science.nasa.gov/apod/"}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
# Aviso opcional por Telegram (só existe na máquina do autor; sem o script, o aviso é ignorado).
NOTIFY_SCRIPT = Path(os.environ.get("WALLPAPER_NASA_NOTIFY_SCRIPT", "C:/Users/jairs/Scripts/telegram_direto.py"))
TASK_NAME = APP_NAME
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / APP_NAME
SOURCE_PATH = APP_DIR / "imagem_nasa_original.jpg"
WALLPAPER_PATH = APP_DIR / "wallpaper_atual.jpg"
METADATA_PATH = APP_DIR / "metadata.json"
LOG_PATH = APP_DIR / "app.log"
USER_AGENT = f"{APP_NAME}/1.0"


def log(message: str) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"{date.today().isoformat()} | {message}\n")


def notify_once_a_day(kind: str, text: str) -> None:
    """Avisa pelo Telegram no máximo uma vez por dia para cada tipo de problema.
    Nunca levanta exceção: o aviso não pode derrubar a atualização do papel de parede."""
    state_path = APP_DIR / "notify_state.json"
    try:
        if not NOTIFY_SCRIPT.exists():
            return
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        today = date.today().isoformat()
        if state.get(kind) == today:
            return
        spec = importlib.util.spec_from_file_location("telegram_direto", NOTIFY_SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # nosec B102 - script local do próprio autor
        ok, detail = module.enviar(f"[Claude] {APP_NAME}\n{text}\nLog: {LOG_PATH}")
        log(f"Aviso Telegram ({kind}): {detail}")
        if ok:
            state[kind] = today
            state_path.write_text(json.dumps(state), encoding="utf-8")
    except Exception as error:  # noqa: BLE001
        log(f"Aviso Telegram falhou ({kind}): {error}")


def request_json(day: date, timeout: int = 20) -> dict:
    params = urllib.parse.urlencode(
        {"api_key": os.environ.get("NASA_API_KEY", "DEMO_KEY"), "date": day.isoformat()}
    )
    request = urllib.request.Request(
        f"{API_URL}?{params}", headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f"A NASA respondeu com o código {response.status}.")
        return json.loads(response.read().decode("utf-8"))


def request_json_with_retries(day: date, attempts: int = 3, delay: float = 5.0) -> dict:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return request_json(day)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < attempts - 1:
                log(f"Falha temporária ao consultar {day.isoformat()} (tentativa {attempt + 1}/{attempts}): {error}")
                time.sleep(delay)
    raise last_error


def is_real_photo(item: dict) -> bool:
    """A API da NASA passou a devolver o logo do site no lugar da foto; só aceita foto de verdade."""
    url = (item.get("hdurl") or item.get("url") or "").lower()
    path = urllib.parse.urlparse(url).path
    return (
        item.get("media_type") == "image"
        and path.endswith(IMAGE_EXTENSIONS)
        and "nasa-logo" not in path
        and "/themes/" not in path
    )


def _fetch_feed_items_once(timeout: int = 20) -> list[dict]:
    """Uma leitura do feed oficial do APOD em science.nasa.gov, do mais novo para o mais antigo."""
    request = urllib.request.Request(FEED_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(2_000_000)
    # Servidor instável (503, CDN) pode devolver uma página HTML de erro no lugar do XML.
    if data.lstrip()[:20].lower().startswith((b"<!doctype html", b"<html")):
        raise RuntimeError("O feed da NASA devolveu uma página HTML em vez do XML (instabilidade temporária do servidor).")
    # Declaração DTD/ENTITY só existe antes do elemento raiz. Feed legítimo não tem; recusar evita bomba de
    # entidades (billion laughs). Só o prólogo é examinado: o texto das notícias pode citar essas palavras.
    primeiro_elemento = re.search(rb"<[A-Za-z_]", data)
    prologo = re.sub(rb"<!--.*?-->", b"", data[: primeiro_elemento.start() if primeiro_elemento else len(data)], flags=re.S).lower()
    if b"<!doctype" in prologo or b"<!entity" in prologo:
        raise RuntimeError("Feed da NASA com declaração DTD/ENTITY recusado.")
    root = ET.fromstring(data)  # nosec B314 - DTD recusado acima, tamanho limitado
    items = []
    for node in root.iter("item"):
        hdurl = (node.findtext("apod:hdurl", default="", namespaces=FEED_NS) or "").strip()
        pub = node.findtext("pubDate", default="")
        try:
            day = parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            continue
        is_image = urllib.parse.urlparse(hdurl).path.lower().endswith(IMAGE_EXTENSIONS)
        items.append(
            {
                "date": day,
                "title": (node.findtext("title", default="") or "").strip(),
                "hdurl": hdurl,
                "url": hdurl,
                "media_type": "image" if is_image else "other",
            }
        )
    return items


def fetch_feed_items(timeout: int = 20, attempts: int = 3, delay: float = 5.0) -> list[dict]:
    """Lê o feed com nova tentativa, como na API: um soluço do servidor não pode derrubar a troca do dia."""
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return _fetch_feed_items_once(timeout)
        except (OSError, RuntimeError, ET.ParseError) as error:
            if "DTD/ENTITY" in str(error):
                raise  # recusa de segurança: insistir não muda nada
            last_error = error
            if attempt < attempts - 1:
                log(f"Falha temporária ao ler o feed da NASA (tentativa {attempt + 1}/{attempts}): {error}")
                time.sleep(delay)
    raise last_error


def find_latest_image_from_feed() -> dict:
    for item in fetch_feed_items():
        if is_real_photo(item):
            return item
    raise RuntimeError("O feed da NASA não trouxe nenhuma imagem recente.")


def find_latest_image(start: date | None = None, lookback: int = 7) -> dict:
    current = start or date.today()
    last_error: Exception | None = None
    for offset in range(lookback + 1):
        try:
            item = request_json_with_retries(current - timedelta(days=offset))
            if is_real_photo(item):
                return item
            if offset == 0 and item.get("media_type") == "image":
                break  # a API respondeu, mas com imagem inválida (logo): usa o feed
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            last_error = error
            if offset == 0:
                break
    try:
        item = find_latest_image_from_feed()
        log(f"API da NASA sem foto válida; usando o feed oficial: {item['date']} | {item['title']}")
        item["fonte"] = "feed"
        return item
    except (OSError, RuntimeError, ValueError, ET.ParseError) as error:
        last_error = error
    if last_error:
        raise RuntimeError(f"Não foi possível consultar a NASA: {last_error}") from last_error
    raise RuntimeError("Não foi encontrada uma imagem recente na NASA.")


def download_and_validate(url: str, destination: Path, timeout: int = 60) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    temp_path: Path | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise RuntimeError(f"Conteúdo inesperado recebido: {content_type}.")
            with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, suffix=".download") as temp:
                temp_path = Path(temp.name)
                shutil.copyfileobj(response, temp)
        with Image.open(temp_path) as image:
            image.verify()
        with Image.open(temp_path) as image:
            converted = ImageOps.exif_transpose(image).convert("RGB")
            converted.save(temp_path, format="JPEG", quality=95, optimize=True)
        os.replace(temp_path, destination)
        temp_path = None
    except (urllib.error.URLError, TimeoutError, UnidentifiedImageError, OSError) as error:
        raise RuntimeError(f"Falha no download ou na validação da imagem: {error}") from error
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass


def display_layout() -> tuple[int, int, int]:
    if os.name != "nt":
        raise RuntimeError("A detecção dos monitores requer Windows.")
    user32 = ctypes.windll.user32
    width = user32.GetSystemMetrics(78)
    height = user32.GetSystemMetrics(79)
    count = user32.GetSystemMetrics(80)
    if width <= 0 or height <= 0:
        raise RuntimeError("O Windows não informou uma área válida para os monitores.")
    return width, height, max(count, 1)


def prepare_panorama(source: Path, destination: Path, size: tuple[int, int]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with Image.open(source) as original:
            normalized = ImageOps.exif_transpose(original).convert("RGB")
            panorama = ImageOps.fit(
                normalized,
                size,
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
        with tempfile.NamedTemporaryFile(
            delete=False, dir=destination.parent, suffix=".panorama"
        ) as temp:
            temp_path = Path(temp.name)
        panorama.save(temp_path, format="JPEG", quality=95, optimize=True)
        os.replace(temp_path, destination)
        temp_path = None
    except (UnidentifiedImageError, OSError) as error:
        raise RuntimeError(f"Não foi possível preparar a imagem panorâmica: {error}") from error
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def set_span_mode() -> None:
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Control Panel\Desktop",
        0,
        winreg.KEY_SET_VALUE,
    ) as key:
        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, "22")
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, "0")


def set_wallpaper(path: Path) -> None:
    if os.name != "nt":
        raise RuntimeError("A troca automática do papel de parede requer Windows.")
    set_span_mode()
    applied = ctypes.windll.user32.SystemParametersInfoW(20, 0, str(path.resolve()), 3)
    if not applied:
        raise ctypes.WinError()


def prepare_and_set_wallpaper(source: Path) -> tuple[int, int, int]:
    width, height, count = display_layout()
    prepare_panorama(source, WALLPAPER_PATH, (width, height))
    set_wallpaper(WALLPAPER_PATH)
    return width, height, count


def save_metadata(item: dict) -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    temp = METADATA_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, METADATA_PATH)


def load_metadata() -> dict:
    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def update_wallpaper() -> tuple[bool, str, dict]:
    previous = load_metadata()
    try:
        item = find_latest_image()
        same_image = item.get("date") == previous.get("date") and item.get("hdurl") == previous.get("hdurl")
        if not same_image or not SOURCE_PATH.exists():
            download_and_validate(item.get("hdurl") or item["url"], SOURCE_PATH)
        width, height, count = prepare_and_set_wallpaper(SOURCE_PATH)
        item["display"] = {"width": width, "height": height, "monitors": count}
        save_metadata(item)
        log(
            f"Imagem aplicada: {item.get('date')} | {item.get('title', '')} | "
            f"{width}x{height} em {count} monitor(es)"
        )
        if item.get("date") == previous.get("date"):
            return True, f"Imagem panorâmica atualizada para {count} monitores.", item
        return True, f"Novo papel de parede panorâmico aplicado em {count} monitores.", item
    except Exception as error:
        log(f"Atualização não realizada: {error}")
        if WALLPAPER_PATH.exists():
            try:
                set_wallpaper(WALLPAPER_PATH)
            except Exception:
                pass
            return False, f"Sem atualização. A imagem anterior foi mantida.\n\n{error}", previous
        return False, f"Não foi possível obter a primeira imagem.\n\n{error}", previous


def executable_command() -> tuple[str, str]:
    if getattr(sys, "frozen", False):
        return str(Path(sys.executable).resolve()), "--background"
    return str(Path(sys.executable).resolve()), f'"{Path(__file__).resolve()}" --background'


def install_schedule() -> None:
    executable, arguments = executable_command()
    ps_script = (
        f"$a=New-ScheduledTaskAction -Execute '{executable.replace(chr(39), chr(39) * 2)}' "
        f"-Argument '{arguments.replace(chr(39), chr(39) * 2)}';"
        "$t=@((New-ScheduledTaskTrigger -AtLogOn),"
        "(New-ScheduledTaskTrigger -Daily -At '09:00'));"
        "$s=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10);"
        f"Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $a -Trigger $t "
        "-Settings $s -Description 'Atualiza diariamente o papel de parede da NASA.' -Force | Out-Null"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "Não foi possível instalar a tarefa.")


def remove_schedule() -> None:
    subprocess.run(
        ["schtasks.exe", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def schedule_exists() -> bool:
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", TASK_NAME],
        capture_output=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return result.returncode == 0


class WallpaperApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("760x660")
        self.minsize(680, 600)
        self.configure(bg="#07111f")
        self.preview: ImageTk.PhotoImage | None = None
        self.status = tk.StringVar(value="Pronto para explorar o universo.")
        self.title_text = tk.StringVar(value="Nenhuma imagem baixada ainda")
        self.details = tk.StringVar(value="")
        self.auto = tk.BooleanVar(value=schedule_exists())
        self._build()
        self._refresh_view(load_metadata())

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Main.TFrame", background="#07111f")
        style.configure("Card.TFrame", background="#101f33")
        style.configure("Title.TLabel", background="#07111f", foreground="#ffffff", font=("Segoe UI", 22, "bold"))
        style.configure("Text.TLabel", background="#101f33", foreground="#dce8f7", font=("Segoe UI", 10))
        style.configure("ImageTitle.TLabel", background="#101f33", foreground="#ffffff", font=("Segoe UI", 14, "bold"))
        style.configure("Accent.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 10))
        style.configure("TCheckbutton", background="#101f33", foreground="#dce8f7")

        root = ttk.Frame(self, padding=24, style="Main.TFrame")
        root.pack(fill="both", expand=True)
        ttk.Label(root, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Uma nova janela para o universo, todos os dias.",
            foreground="#7fb7ff",
            background="#07111f",
            font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(2, 18))

        card = ttk.Frame(root, padding=16, style="Card.TFrame")
        card.pack(fill="both", expand=True)
        self.image_label = tk.Label(card, bg="#08111d", fg="#8ca3bd", text="Prévia da NASA", font=("Segoe UI", 14))
        self.image_label.pack(fill="both", expand=True)
        ttk.Label(card, textvariable=self.title_text, style="ImageTitle.TLabel", wraplength=660).pack(anchor="w", pady=(14, 4))
        ttk.Label(card, textvariable=self.details, style="Text.TLabel", wraplength=660).pack(anchor="w")

        controls = ttk.Frame(card, style="Card.TFrame")
        controls.pack(fill="x", pady=(16, 0))
        self.update_button = ttk.Button(controls, text="Atualizar agora", style="Accent.TButton", command=self.start_update)
        self.update_button.pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Atualizar automaticamente todos os dias",
            variable=self.auto,
            command=self.toggle_schedule,
        ).pack(side="left", padx=18)
        ttk.Label(root, textvariable=self.status, foreground="#a9bdd5", background="#07111f", wraplength=700).pack(
            anchor="w", pady=(14, 0)
        )

    def _refresh_view(self, item: dict) -> None:
        self.title_text.set(item.get("title") or "Nenhuma imagem baixada ainda")
        parts = [item.get("date", "")]
        if item.get("copyright"):
            parts.append(f"Crédito: {item['copyright']}")
        display = item.get("display", {})
        if display.get("width") and display.get("height"):
            parts.append(
                f"Panorâmica: {display['width']} × {display['height']} "
                f"em {display.get('monitors', 1)} monitores"
            )
        self.details.set("  •  ".join(part for part in parts if part))
        if WALLPAPER_PATH.exists():
            try:
                with Image.open(WALLPAPER_PATH) as source:
                    image = ImageOps.contain(source.convert("RGB"), (680, 390))
                self.preview = ImageTk.PhotoImage(image)
                self.image_label.configure(image=self.preview, text="")
            except OSError:
                pass

    def start_update(self) -> None:
        self.update_button.configure(state="disabled")
        self.status.set("Consultando a NASA e baixando a imagem em alta resolução...")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self) -> None:
        success, message, item = update_wallpaper()
        self.after(0, self._finish_update, success, message, item)

    def _finish_update(self, success: bool, message: str, item: dict) -> None:
        self.update_button.configure(state="normal")
        self.status.set(message.replace("\n\n", " "))
        self._refresh_view(item)
        if not success:
            messagebox.showwarning(APP_NAME, message)

    def toggle_schedule(self) -> None:
        try:
            if self.auto.get():
                install_schedule()
                self.status.set("Atualização automática ativada para 9h e ao entrar no Windows.")
            else:
                remove_schedule()
                self.status.set("Atualização automática desativada.")
        except Exception as error:
            self.auto.set(schedule_exists())
            messagebox.showerror(APP_NAME, str(error))


def main() -> int:
    enable_dpi_awareness()
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--background", action="store_true")
    parser.add_argument("--install-schedule", action="store_true")
    args = parser.parse_args()
    if args.install_schedule:
        install_schedule()
        return 0
    if args.background:
        success, message, item = update_wallpaper()
        if not success:
            notify_once_a_day("falha", f"Não consegui trocar o papel de parede hoje.\n{message}")
        elif item.get("fonte") == "feed":
            notify_once_a_day(
                "api_degradada",
                "A API oficial do APOD não devolveu uma foto válida; usei o feed science.nasa.gov. "
                "O papel de parede foi trocado, mas a API precisa de atenção.",
            )
        return 0 if success else 1
    APP_DIR.mkdir(parents=True, exist_ok=True)
    WallpaperApp().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
