# Project: BetBus Sync Localization
> Cập nhật: 2026-06-23

## Mục tiêu
Sync 1 chiều Google Sheet → Lark Base (Bitable). 2 table, mỗi table ~5 cột, ~4000 row. Mirror 100% số row + content. Chạy mỗi 15 phút trên GitHub Actions.

## Quyết định đã chốt
| Vấn đề | Phương án chọn | Lý do |
|--------|----------------|-------|
| Đích sync | Lark Base (Bitable) | User chốt |
| Chiều sync | 1 chiều GSheet → Lark | User chốt |
| Host | GitHub Actions (cron 15 phút) | Free, không cần server |
| Strategy | Mirror 100% theo `__row_idx` | User yêu cầu Lark = GSheet về số row + content |
| Duplicate key | Sync cả 2 row, đánh dấu `__dup_warning` | User chốt |
| Tần suất | 15 phút | Cron GitHub stable ở mức này |
| Ngôn ngữ | Python | Lark + Google SDK tốt |

## Đang làm
- [ ] #7 — Verify cron 15 phút chạy ổn định (theo dõi sau)
- [ ] #8 — Sau khi ổn: regenerate Lark App Secret + Google SA key (do lộ trong chat)

## Backlog

## Hoàn thành
- [x] #1 — Scaffold project (sync.py, lark_client, gsheet_client, workflow YAML, README)
- [x] #2 — Auto-tạo Lark field theo header GSheet (không cần user tạo trước)
- [x] #3 — Google Service Account + share GSheet
- [x] #4 — Lark Custom App + scope bitable:app + wiki:wiki:readonly
- [x] #5 — GitHub repo lstlalesontungg/betbus_sync_localization + 2 secrets
- [x] #6 — workflow_dispatch test PASS (www: 4451, app: 2047 dup=1)
- [x] #9 — Đổi primary field Lark thành `key`
- [x] #10 — Auto resolve wiki_token → app_token
- [x] #11 — Sync sheet 3 (multi-tab merged): 6780 row, 387 dup group
- [x] #12 — Telegram notify mỗi sync run (commit 82c379a, bot @letungsbot → group BÁO CÁO CÁ NHÂN)
