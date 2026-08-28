import os
import glob
import json
import subprocess
import time
from playwright.sync_api import sync_playwright

def cleanup_old_videos(allowed_files):
    """Deleta qualquer arquivo de vídeo que não esteja na lista dos 8 permitidos"""
    for file_path in glob.glob("*.mp4"):
        if file_path not in allowed_files:
            try:
                os.remove(file_path)
                print(f"🗑️ Arquivo antigo removido: {file_path}")
            except Exception as e:
                print(f"Erro ao remover {file_path}: {e}")

def main():
    cookies_raw = os.environ.get("INSTAGRAM_COOKIES", "")
    cookie_file = "cookies.txt"
    with open(cookie_file, "w", encoding="utf-8") as f:
        f.write(cookies_raw)

    playwright_cookies = []
    for line in cookies_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            domain, _, path, secure, expires, name, value = parts[:7]
            playwright_cookies.append({
                "name": name,
                "value": value,
                "domain": domain,
                "path": path,
                "secure": secure.lower() == "true",
                "expires": float(expires) if expires.isdigit() else -1
            })

    username = "goldfitnesssl.centro"
    target_count = 8
    reels_urls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        
        if playwright_cookies:
            context.add_cookies(playwright_cookies)

        page = context.new_page()
        print(f"Acessando perfil de @{username}...")

        # Tenta primeiro na aba /reels/, se não achar tenta no perfil direto
        for target_url in [f"https://www.instagram.com/{username}/reels/", f"https://www.instagram.com/{username}/"]:
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(6)

                for _ in range(3):
                    page.evaluate("window.scrollBy(0, 1000);")
                    time.sleep(2)

                links = page.locator("a[href*='/reel/'], a[href*='/p/']").all()
                for l in links:
                    href = l.get_attribute("href")
                    if href:
                        full_url = f"https://www.instagram.com{href}" if href.startswith("/") else href
                        if full_url not in reels_urls:
                            reels_urls.append(full_url)
                    if len(reels_urls) >= target_count:
                        break

                if len(reels_urls) > 0:
                    break
            except Exception as e:
                print(f"Tentativa em {target_url} falhou: {e}")

        browser.close()

    print(f"Total de posts localizados: {len(reels_urls)}")
    if not reels_urls:
        print("Nenhum post foi identificado.")
        return

    posts_data = []
    allowed_videos = [f"video_{i}.mp4" for i in range(1, target_count + 1)]

    for idx, reel_url in enumerate(reels_urls[:target_count], start=1):
        print(f"\n--- Processando Post #{idx}: {reel_url} ---")
        output_filename = f"video_{idx}.mp4"

        caption = ""
        try:
            desc_cmd = [
                "yt-dlp",
                "--cookies", cookie_file,
                "--no-check-certificates",
                "--dump-json",
                reel_url
            ]
            info_res = subprocess.run(desc_cmd, capture_output=True, text=True)
            if info_res.stdout:
                info_json = json.loads(info_res.stdout)
                caption = info_json.get("description") or info_json.get("title") or ""
        except Exception as e:
            print(f"Erro ao capturar legenda: {e}")

        cmd = [
            "yt-dlp",
            "--cookies", cookie_file,
            "--no-check-certificates",
            "--merge-output-format", "mp4",
            "-f", "bestvideo+bestaudio/best",
            "-o", output_filename,
            "--force-overwrites",
            reel_url
        ]
        subprocess.run(cmd, capture_output=True, text=True)

        posts_data.append({
            "id": idx,
            "url": reel_url,
            "video_file": output_filename,
            "caption": caption.strip() if caption else "Confira as novidades e treinos da Gold Fitness Centro.",
            "updated_at": time.strftime("%d/%m/%Y às %H:%M")
        })

    cleanup_old_videos(allowed_videos)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)

    # Remove o arquivo temporário de cookies após a execução
    if os.path.exists(cookie_file):
        os.remove(cookie_file)

    print("\n✅ Concluído com sucesso!")

if __name__ == "__main__":
    main()
