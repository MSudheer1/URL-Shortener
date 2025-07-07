import qrcode
import io
import base64

async def generate_and_cache_qr(url: str, redis):
    img = qrcode.make(url)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Convert to base64 to store in Redis (or use binary with `set(name, value, encode=False)`)
    b64_qr = base64.b64encode(buffer.read()).decode()

    qr_key = f"qr:{url}"  # e.g., qr:http://surl/sign/abc123
    await redis.set(qr_key, b64_qr, ex=86400)  # cache for 1 day
