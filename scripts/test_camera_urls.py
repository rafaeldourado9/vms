"""
Script para testar conectividade com URLs RTSP/RTMP de câmeras.
Uso: python -m scripts.test_camera_urls
"""
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Lista de URLs fornecidas pelo usuário
CAMERA_URLS = [
    # RTSP - Intelbras
    "rtsp://admin:Camerite123@45.236.226.70:6044/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:Camerite123@45.236.226.70:6045/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:Camerite123@45.236.226.71:6046/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:Camerite123@45.236.226.71:6047/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:Camerite123@45.236.226.72:6048/cam/realmonitor?channel=1&subtype=0",
    "rtsp://admin:Camerite123@45.236.226.72:6049/cam/realmonitor?channel=1&subtype=0",
    
    # RTMP - Intelbras
    "rtmp://inst-3gmrv-srs-rtmp-intelbras.camerite.services:1935/record/7KOM27155085F.stream",
    "rtmp://inst-oifvp-srs-rtmp-intelbras.camerite.services:1935/record/7KOM2715585AK.stream",
    "rtmp://inst-3gmrv-srs-rtmp-intelbras.camerite.services:1935/record/7KOM2715805PF.stream",
    
    # RTSP - Hikvision
    "rtsp://admin:Camerite@170.84.217.71:608/h264/ch1/main/av_stream",
    "rtsp://admin:Camerite@170.84.217.83:608/h264/ch1/main/av_stream",
    "rtsp://admin:Camerite@170.84.217.84:603/h264/ch1/main/av_stream",
    "rtsp://admin:Camerite@186.226.193.111:600/h264/ch1/main/av_stream",
    "rtsp://admin:Camerite@186.226.193.111:601/h264/ch1/main/av_stream",
    
    # RTMP - Hikvision
    "rtmp://inst-ax9xa-srs-rtmp-hik-pro-connect.camerite.services:1935/record/FC2487237.stream",
    "rtmp://inst-jxz3f-srs-rtmp-hik-pro-connect.camerite.services:1935/record/FC2487838.stream",
    "rtmp://inst-zmqsq-srs-rtmp-hik-pro-connect.camerite.services:1935/record/FC2487653.stream",
]


def test_rtsp_url(url: str, timeout: int = 5) -> dict:
    """Testa uma URL RTSP usando ffprobe."""
    try:
        # Extrair host para logging
        parsed = urlparse(url)
        host = parsed.hostname
        
        # Usar ffprobe para verificar se o stream está acessível
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-rtsp_transport", "tcp",
            "-timeout", str(timeout * 1000000),  # microseconds
            "-i", url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
            
            return {
                "url": url,
                "host": host,
                "status": "OK",
                "video_streams": len(video_streams),
                "codec": video_streams[0].get("codec_name", "unknown") if video_streams else None,
            }
        else:
            return {
                "url": url,
                "host": host,
                "status": "FAIL",
                "error": "ffprobe failed",
            }
            
    except subprocess.TimeoutExpired:
        return {
            "url": url,
            "host": parsed.hostname if 'parsed' in locals() else "unknown",
            "status": "TIMEOUT",
        }
    except FileNotFoundError:
        return {
            "url": url,
            "host": urlparse(url).hostname,
            "status": "ERROR",
            "error": "ffprobe not found. Install ffmpeg first.",
        }
    except Exception as e:
        return {
            "url": url,
            "host": urlparse(url).hostname,
            "status": "ERROR",
            "error": str(e),
        }


def test_rtmp_url(url: str, timeout: int = 5) -> dict:
    """Testa uma URL RTMP usando ffprobe."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-timeout", str(timeout * 1000000),
            "-i", url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 2
        )
        
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            video_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"]
            
            return {
                "url": url,
                "host": host,
                "status": "OK",
                "video_streams": len(video_streams),
                "codec": video_streams[0].get("codec_name", "unknown") if video_streams else None,
            }
        else:
            return {
                "url": url,
                "host": host,
                "status": "FAIL",
                "error": "ffprobe failed",
            }
            
    except subprocess.TimeoutExpired:
        return {
            "url": url,
            "host": parsed.hostname if 'parsed' in locals() else "unknown",
            "status": "TIMEOUT",
        }
    except FileNotFoundError:
        return {
            "url": url,
            "host": urlparse(url).hostname,
            "status": "ERROR",
            "error": "ffprobe not found. Install ffmpeg first.",
        }
    except Exception as e:
        return {
            "url": url,
            "host": urlparse(url).hostname,
            "status": "ERROR",
            "error": str(e),
        }


def test_url(url: str) -> dict:
    """Testa uma URL RTSP ou RTMP."""
    if url.startswith("rtsp://"):
        return test_rtsp_url(url)
    elif url.startswith("rtmp://"):
        return test_rtmp_url(url)
    else:
        return {"url": url, "status": "UNKNOWN", "error": "Protocolo não suportado"}


def main():
    print("=" * 80)
    print("TESTE DE CONECTIVIDADE - CÂMERAS RTSP/RTMP")
    print("=" * 80)
    print()
    
    # Verificar se ffprobe está instalado
    try:
        subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=3)
    except FileNotFoundError:
        print("❌ ERRO: ffprobe não encontrado!")
        print("   Instale o ffmpeg/ffprobe primeiro:")
        print("   - Windows: choco install ffmpeg")
        print("   - Linux: sudo apt install ffmpeg")
        print("   - Mac: brew install ffmpeg")
        sys.exit(1)
    
    print(f"Testando {len(CAMERA_URLS)} câmeras...")
    print()
    
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(test_url, url): url for url in CAMERA_URLS}
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            
            # Status icon
            if result["status"] == "OK":
                icon = "✅"
            elif result["status"] == "TIMEOUT":
                icon = "⏱️"
            elif result["status"] == "FAIL":
                icon = "❌"
            else:
                icon = "⚠️"
            
            host = result.get("host", "?")
            status = result["status"]
            codec = result.get("codec", "")
            codec_info = f" ({codec})" if codec else ""
            
            print(f"{icon} {host:50s} {status}{codec_info}")
    
    # Resumo
    print()
    print("=" * 80)
    print("RESUMO:")
    ok_count = sum(1 for r in results if r["status"] == "OK")
    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    timeout_count = sum(1 for r in results if r["status"] == "TIMEOUT")
    error_count = sum(1 for r in results if r["status"] == "ERROR")
    
    print(f"  ✅ Online: {ok_count}")
    print(f"  ❌ Offline: {fail_count}")
    print(f"  ⏱️  Timeout: {timeout_count}")
    print(f"  ⚠️  Erro: {error_count}")
    print(f"  📊 Total: {len(results)}")
    print("=" * 80)
    
    # URLs que funcionaram
    if ok_count > 0:
        print()
        print("URLs ONLINE (prontas para uso):")
        for r in results:
            if r["status"] == "OK":
                print(f"  ✓ {r['url']}")
    
    # URLs que falharam
    if fail_count + timeout_count > 0:
        print()
        print("URLs OFFLINE (verificar):")
        for r in results:
            if r["status"] in ("FAIL", "TIMEOUT"):
                print(f"  ✗ {r['url']}")
    
    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
