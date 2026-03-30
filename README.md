# 🤖 Trading Signal Bot — Telegram

Bot phân tích kỹ thuật đa khung thời gian dựa trên:
**RSI + EMA Cross (21/49) + Stochastic RSI + MACD**

Khung thời gian: **15m · 1h · 4h · 1d**
Dữ liệu: **Binance (miễn phí, không cần API key)**

---

## 📋 Tính năng

| Lệnh | Mô tả |
|------|-------|
| `/start` | Menu chính với nút bấm inline |
| `/analyze BTCUSDT` | Phân tích đầy đủ 4 khung TF |
| `/consensus BTCUSDT` | Kiểm tra đồng thuận BUY/SELL |
| `/signal BTCUSDT 1h` | Tín hiệu khung cụ thể |
| `/add SOLUSDT` | Thêm cặp vào watchlist |
| `/remove SOLUSDT` | Xóa khỏi watchlist |
| `/watchlist` | Xem danh sách theo dõi |
| `/alert on/off` | Bật/tắt tự động gửi tín hiệu |
| `/alert interval 30` | Kiểm tra mỗi N phút |
| `/params` | Xem tham số chỉ báo |
| `/setrsi 14` | Thay đổi RSI period |
| `/status` | Trạng thái bot |
| Chat tự nhiên | _"BTC thế nào?"_ → tự phân tích |

---

## 🚀 Hướng dẫn Deploy

### Bước 1 — Tạo Bot Telegram

1. Mở Telegram, tìm **@BotFather**
2. Gõ `/newbot` → đặt tên bot
3. Copy **token** (dạng `123456:ABCdef...`)

### Bước 2 — Đẩy code lên GitHub

```bash
git init
git add .
git commit -m "init: trading signal bot"
git remote add origin https://github.com/YOUR_USERNAME/trading-bot.git
git push -u origin main
```

### Bước 3 — Deploy lên Railway

1. Vào [railway.app](https://railway.app) → **New Project**
2. Chọn **Deploy from GitHub repo** → chọn repo vừa tạo
3. Vào tab **Variables** → thêm:
   ```
   TELEGRAM_BOT_TOKEN = your_token_here
   ```
4. Railway tự động build và chạy!

### Bước 4 — Kết nối GitHub Actions (tùy chọn)

Để tự động deploy khi push code:

1. Vào Railway → **Account Settings → Tokens** → tạo token mới
2. Vào GitHub repo → **Settings → Secrets → Actions**
3. Thêm secret: `RAILWAY_TOKEN` = token từ Railway

---

## ⚙️ Cấu hình

### Tham số chỉ báo (mặc định từ Pine Script gốc)

| Tham số | Giá trị |
|---------|---------|
| RSI Period | 7 |
| EMA Fast | 21 |
| EMA Slow | 49 |
| Stoch Length | 14 |
| OB / OS | 70 / 30 |
| Stoch OB / OS | 80 / 20 |
| MACD | 12 / 26 / 9 |
| Lookback Bars | 8 |

Thay đổi qua lệnh `/setrsi`, hoặc sửa `DEFAULT_PARAMS` trong `src/state.py`.

---

## 📊 Logic tín hiệu

### Tín hiệu BUY (Combined Mode)
- EMA 21 cross trên EMA 49 (trong vòng 8 bar)
- Stoch %K cross trên %D
- Stoch K < 80 (chưa quá mua)

### Tín hiệu SELL
- EMA 21 cross dưới EMA 49 (trong vòng 8 bar)
- Stoch %K cross dưới %D
- Stoch K > 20 (chưa quá bán)

### Điểm sức mạnh (0-5)
1. EMA cross trong window
2. Stoch cross
3. Stoch K < 50 (buy) / > 50 (sell)
4. RSI < 50 (buy) / > 50 (sell)
5. MACD bullish (buy) / bearish (sell)

### Đồng thuận đa TF
- **MẠNH**: 4/4 TF cùng tín hiệu
- **TRUNG BÌNH**: 3/4 TF
- **YẾU**: 2/4 TF
- **WAIT**: < 2 TF

---

## 🔧 Chạy local

```bash
# Tạo môi trường ảo
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Cài thư viện
pip install -r requirements.txt

# Tạo file .env
cp .env.example .env
# Điền TELEGRAM_BOT_TOKEN vào .env

# Chạy bot
python bot.py
```

---

## ⚠️ Lưu ý

> Bot chỉ hỗ trợ phân tích kỹ thuật, **không phải lời khuyên đầu tư**.
> Luôn tự nghiên cứu và quản lý rủi ro trước khi giao dịch.
