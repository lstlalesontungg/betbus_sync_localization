# BetBus Sync Localization

Sync 1 chiều Google Sheet → Lark Base mỗi 15 phút qua GitHub Actions.

## Cách hoạt động

- Đọc 2 tab GSheet → mirror vào 2 table Lark Base.
- Mirror 100%: số row + content Lark luôn = GSheet.
- Diff theo field `__row_idx` (index row trong GSheet, 1-based, không tính header).
- Trùng key (cột localization key) → vẫn sync cả 2 row, đánh dấu vào cột `__dup_warning`.

## Setup 1 lần

### 1. Google Service Account

1. Vào https://console.cloud.google.com/ → tạo project (hoặc dùng cái có sẵn).
2. Enable API `Google Sheets API`.
3. IAM & Admin → Service Accounts → Create Service Account.
4. Tạo Key → JSON → tải về file.
5. Mở Google Sheet cần sync → Share → paste email service account (dạng `xxx@xxx.iam.gserviceaccount.com`) → role Viewer.

### 2. Lark Custom App

1. Vào https://open.larksuite.com/app (hoặc https://open.feishu.cn/app nếu dùng Feishu CN).
2. Create Custom App → đặt tên.
3. Permissions & Scopes → add:
   - `bitable:app` (read + write)
4. Publish version → submit (admin tenant approve).
5. Credentials & Basic Info → copy **App ID** + **App Secret**.

### 3. Lark Base setup

Mở Lark Base cần sync. Với MỖI table:

- Tạo sẵn các field tương ứng với cột GSheet (cùng tên).
- Thêm 2 field hệ thống:
  - `__row_idx` — type **Number**
  - `__dup_warning` — type **Text**
- Cấp quyền cho app: Lark Base → settings ⚙ → Permissions → add custom app vừa tạo → Can edit.
- Copy `app_token` (chuỗi `bascn...` hoặc `bsctn...` trong URL Lark Base) + `table_id` (chuỗi `tbl...` trong URL khi mở table).

### 4. GitHub repo + secrets

1. Tạo repo (private được, < 2000 phút/tháng).
2. Push code này lên.
3. Repo → Settings → Secrets and variables → Actions → New repository secret. Tạo 2 secret:

   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste nguyên nội dung file JSON service account.
   - `SYNC_CONFIG_YAML` — paste nguyên nội dung file YAML (xem `config.example.yaml`), điền giá trị thật.

### 5. Test

- Repo → Actions → "Sync GSheet to Lark Base" → Run workflow (workflow_dispatch).
- Xem log. Nếu OK, cron sẽ tự chạy mỗi 15 phút.

## Chạy local (dev)

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml      # điền giá trị
export GOOGLE_SERVICE_ACCOUNT_FILE=./service_account.json
python sync.py
```

## Quota / cost

- GitHub Actions free 2000 phút/tháng (private). Run ~30s × 4/giờ × 24 × 30 ≈ 1440 phút → vừa đủ.
- Lark Open API rate limit: 50 QPS. Batch 500 record/request → 4000 row = 8 batch/op → an toàn.

## Limitation

- Lark field type phải match: text/number/multi-select. Type lạ (attachment, link, person) hiện chưa hỗ trợ → để dạng text/number ở GSheet.
- Field tên có ký tự đặc biệt nên tránh.
- Row order Lark Base không cố định theo `__row_idx` — nếu cần view theo thứ tự GSheet, tạo View sort ASC theo `__row_idx`.
