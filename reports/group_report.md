# Group Report — Day 06 Data Lab (Field-to-Release PoC)

> Mọi con số trong báo cáo này lấy từ file do script sinh ra: `out/*/run_info.json`,
> `reports/metrics_*_internal.json`, `reports/table1_internal_baseline_vs_poc.md`,
> `reports/table2_internal_baseline_vs_engine_only.md`. Không gõ tay con số nào.

## 00 · Header

| Mục | Giá trị |
|---|---|
| Group ID | G07 |
| Challenge | T09 · Multi-Market Privacy Decision Gate |
| Thành viên + vai trò | 1. **Nguyễn Hữu Thịnh** (2A202603308) — Lead / Integrator: `.gitattributes`, `configs/lab.yaml`, nối dây 5 bước trong `src/pipeline.py`, lệnh one-command, đóng tag · 2. **Đinh Hữu Thái An** — Policy & legal research: `configs/policy/privacy_policy_v1.yaml`, tra số điều và ghi nguồn · 3. **Nguyễn Minh Triết** — Core algorithm: `src/policy/engine.py`, rule DSL, precedence, `effective_date`, field alias · 4. **Phạm Thị Lương** — Baseline & metric: `src/baselines/`, chạy evaluate và compare, `reports/metrics_*` và hai bảng so sánh · 5. **Đoàn Thị Ánh Hậu** — QA & test: `tests/test_policy_engine.py`, `tools/field_coverage.py`, gold nội bộ, kiểm provenance và hai guard · 6. **Phạm Hữu Minh** (2A202603330) — Human review & report: vòng review, audit checklist, báo cáo, demo; là người ký duyệt ghi trong `out/poc/audit_log.jsonl` |
| Git URL | điền sau khi push; repo hiện là bản clone template `VinUni-AI20k/K5-Day6-L2-DataGovernanceAndPrivacy`, commit gốc `b0ce8bf` |
| Tag `demo-180m` (commit) | chưa tạo |
| Tag `final-24h` (commit) | chưa tạo |
| Deadline (giờ VN) | theo LMS Day 06 |
| Policy đã chốt | `configs/policy/privacy_policy_v1.yaml`, version **`g07-1.1.0`**, sha256 `ef49790a9ef3c744…`, `as_of: 2026-11-14`, 21 rule. Bản chốt đầu tiên là `g07-1.0.0` (19 rule); v1.1.0 sửa một lỗi thật do reviewer ngoài nhóm chỉ ra, xem mục 06 failure case 3 và changelog trong chính file rule |

## 01 · Problem statement

Ai chịu hậu quả khi cổng này sai: người đi đường và người trong khoang xe bị thu hình. Dữ liệu đã nằm trong
tập train rồi mới phát hiện sai căn cứ pháp lý thì không "thu lại" được nữa. Phía công ty thì đứng trước
rủi ro phải xoá dataset và huỷ cả model đã train trên đó.

Điểm nghẽn cụ thể: một đợt thu dữ liệu ADAS chạy trên nhiều thị trường, mỗi nơi một bộ nghĩa vụ khác nhau.
VN không có căn cứ "lợi ích hợp pháp". EU có, nhưng siết việc chuyển dữ liệu ra ngoài EEA. California không
dùng khái niệm lawful basis mà siết notice và sensitive personal information. Người phụ trách không thể nhớ
hết, còn một checklist "đã có consent chưa" thì bỏ sót phần lớn nghĩa vụ.

Đầu vào thành đầu ra: 12 hồ sơ case JSON (market, data_types, lawful_basis, consent, notice, storage,
transfer, retention, DPIA, ambiguity_notes) cho ra `out/poc/decisions.csv` với `case_id, decision,
reason_codes`, kèm rule id, nguồn điều khoản và một audit checklist để người phụ trách ký.

Tiêu chí quyết định, chốt trước khi chạy eval:

- **GO** — không rule nào bắn, và không có ghi chú mơ hồ nào cần legal.
- **REWORK** — chỉ có lỗi sửa được mà không phải đổi căn cứ pháp lý: retention chưa đặt hoặc quá dài,
  consent gộp, thiếu bản ghi consent, dữ liệu SPI cần giới hạn mục đích.
- **HOLD** — thiếu căn cứ pháp lý, chuyển dữ liệu xuyên biên giới không có cơ chế, thiếu DPIA, dữ liệu thô
  nhận dạng được nằm trên cloud, không mã hoá, có thể có trẻ em, hoặc hồ sơ mơ hồ phải hỏi legal.
- Thứ tự ưu tiên **HOLD cao hơn REWORK cao hơn GO**; `NOTE` không bao giờ đổi quyết định.

Giả định cần DPO hoặc legal xác nhận: số điều của Luật 91/2025 và NĐ 356/2025 lấy theo bản dịch tiếng Anh
trên luatvietnam, chưa đối chiếu công báo; ngưỡng retention 365 ngày là quyết định của nhóm, không phải con
số trong luật; rule EU về in-cabin video dựa trên guideline EDPB 01/2020, tức là diễn giải chứ không phải
điều luật. Mỗi rule mang cờ `needs_legal_review` và `confidence` để chỗ nào là suy luận thì đọc ra ngay.

## 02 · Data & provenance

| Split | N | Nguồn / link | License | Synthetic? |
|---|---|---|---|---|
| dev | 8 (CASE-01…08) | `fixtures/t09_privacy_gate/cases/` | CC0-1.0 | có, `tools/make_fixtures.py` seed 42 sinh ra |
| eval | 4 (CASE-09…12) | cùng thư mục, gold nằm ở repo giảng viên | CC0-1.0 | có |

- Schema: theo bảng field trong `docs/tracks/T09.md`; nhóm không thêm field nào vào case.
- Seed 42 cho mọi run. Split do đề bài cố định, nhóm không chia lại.
- `manifest.csv` verified: **có** — `python -m tools.verify_manifests` cho `14 manifests, 0 failing`.
- Dữ liệu thật: không dùng, `docs/tracks/T09.md` ghi "Không cần". Repo không có ảnh người thật hay biển số thật.

**Một lỗi provenance đã gặp và đã xử lý, đáng ghi vì nhóm nào chạy Windows cũng gặp:** ngay sau khi clone,
cả 14 manifest đều FAIL hash. Nguyên nhân không phải dữ liệu sai mà là Git: máy đặt `core.autocrlf=true` nên
mọi file text bị đổi LF thành CRLF khi checkout, trong khi sha256 trong manifest tính trên bản LF. Kiểm
chứng: hash lại `cases/CASE-01.json` sau khi chuẩn hoá về LF ra đúng chuỗi
`2b7eeb4a89d4022a152443ddd249c0a80872f56eed8ca057f54e67f3a2f6e528` ghi trong manifest. Cách xử lý: thêm
`.gitattributes` (`* text=auto eol=lf`), đặt `core.autocrlf=false` cho repo, chuẩn hoá lại 264 file text.
Sau đó 14 manifest OK và `pytest` hết fail. Vì `strict_provenance: true` nên nếu không sửa thì pipeline dừng
ngay ở bước load với exit code 2, tức là guard hoạt động đúng chứ không phải lỗi của lab.

## 03 · Research & design

| Nguồn | Ngày xem | Dùng vào đâu |
|---|---|---|
| Luật BVDLCN 91/2025/QH15 và NĐ 356/2025, bản dịch luatvietnam | 2026-11-13 | R-VN-01 đến R-VN-03: VN không có legitimate interest, hồ sơ đánh giá tác động chuyển dữ liệu ra nước ngoài, DPIA |
| GDPR (EUR-Lex), Chương V và các Điều 5, 6, 7, 25, 32, 35 | 2026-11-14 | R-XB-01, R-EU-01 đến R-EU-03, R-RET-*, R-SEC-* |
| CCPA/CPRA mục 1798.100 và 1798.121 | 2026-11-14 | R-CA-01 notice at collection, R-CA-02 sensitive personal information |
| EDPB Guidelines 01/2020 connected vehicles | 2026-11-14 | R-EU-02: in-cabin video dưới legitimate interest cần balancing test trên giấy |
| DPDP Act 2023 và DPDP Rules 2025 (Ấn Độ) | 2026-11-14 | R-IN-01 với `effective_date: 2027-05-13`, R-MIN-01 về trẻ em |
| Singapore PDPA mục 26 | 2026-11-14 | R-SG-01 transfer limitation |

Vì sao chọn rule engine thay vì model: có 12 case và nhãn ẩn chỉ 4 case, không đủ để học. Quan trọng hơn,
mỗi quyết định phải chỉ ra được *điều nào* của *văn bản nào*. Một classifier cho ra xác suất thì không ai ký
được. Rule file là dữ liệu có version, luật sư đọc được mà không cần đọc Python.

Luồng chạy: `cases/*.json` cộng `privacy_policy_v1.yaml` vào engine, engine chấm từng case (rule theo market
cộng rule dùng chung), risk score xếp hàng review, người phụ trách quyết định, override ghi vào audit log,
cuối cùng là quyết định cho cả lô kèm audit checklist.

Ba quyết định thiết kế đáng nói:

1. **Không dùng `eval()` cho biểu thức rule.** `policy_example.yaml` của đề viết điều kiện dạng chuỗi Python
   (`when: "transfer.cross_border and ..."`). Nhóm đổi sang DSL có cấu trúc (`field`, `op`, `value`, lồng
   `all` / `any` / `none`): file rule không thể chạy code tuỳ ý, và sai cú pháp thì lộ ra lúc load.
2. **Rule sai thì dừng, không bỏ qua.** Thiếu `source`, thiếu `reason_code`, trùng id, operator lạ, rule
   không có điều kiện nào, tất cả đều làm `load_policy` raise. Một rule âm thầm không bắn chính là failure
   mode mà track này nói tới: metric vẫn ra số đẹp trong khi cổng đã mở.
3. **Luật chưa có hiệu lực thì ghi chú, không tính là vi phạm.** Rule có `effective_date` trong tương lai bị
   hạ xuống `NOTE` và đẩy vào cột `upcoming_obligations`, như CASE-09 với mốc DPDP 13/05/2027. Đây là yêu cầu
   ở mục 8 của `docs/tracks/T09.md`, và có test cho cả hai chiều: hôm nay là NOTE, sau ngày hiệu lực là HOLD.

## 04 · Baseline vs PoC

- **Baseline A** `src.baselines.consent_only` — có consent thì GO. Chạy 12 case, 4 GO, 0.0247 s.
- **Baseline B** `src.baselines.hold_all` — HOLD tất cả, để chứng minh primary metric không đọc một mình được.
- **PoC** `src.pipeline` với policy `g07-1.1.0` — 21 rule, 21 finding, engine ra HOLD 10 và GO 2; vòng review
  của người phụ trách giữ nguyên cả 12 quyết định (8 case được duyệt, 0 case bị đổi). Chạy 0.1786 s, 12 case,
  seed 42, offline.
- Cùng pool 12 case, cùng budget B = 12, cùng seed 42, cùng máy: **xác nhận**. Ba run đều ghi `config_hash`
  và `git_sha` vào `run_info.json` (`b0ce8bf`).

**Bảng 1 · Baseline A so với PoC sau review**, sinh bởi `python -m src.compare`, chấm trên gold nội bộ 8 case dev:

| Metric (unit) | Baseline | PoC | Δ và chú thích |
|---|---|---|---|
| **Critical-miss Rate** (case rủi ro bị cho GO / case rủi ro) | 0.4286 (3/7) | 0.0000 (0/7) | giảm 0.4286, giảm là tốt |
| High-risk HOLD Recall | 0.5714 | 1.0000 | tăng 0.4286 |
| False HOLD rate, guardrail 0.5 | 1.0000 (1/1) | 0.0000 (0/1) | baseline FAIL, PoC PASS |
| Exact decision accuracy | 0.5000 | 1.0000 | tăng 0.5000, N = 8 |
| Reason-code match (risky) | 0.0000 | 1.0000 | baseline = 0, vì baseline không có reason code thật |
| Runtime / 100 items | 0.2058 s | 1.4883 s | chậm hơn khoảng 7 lần nhưng vẫn dưới 2 giây cho 100 case, CPU i7-13620H |

**Bảng 1b · ablation, PoC khi bỏ vòng review** (`reports/table2_internal_baseline_vs_engine_only.md`):

| Metric | Baseline A | PoC engine-only | PoC sau review |
|---|---|---|---|
| Critical-miss Rate | 0.4286 | 0.0000 | 0.0000 |
| False HOLD rate | 1.0000 | 0.0000 | 0.0000 |
| Guardrail 0.5 | FAIL | PASS | PASS |
| Exact decision accuracy | 0.5000 | 1.0000 | 1.0000 |

Hai cột PoC giống nhau, vì ở vòng duyệt hiện tại người phụ trách không đổi quyết định nào của engine. Ở vòng
duyệt đầu tiên thì khác: lúc đó người duyệt escalate CASE-06 và làm false HOLD nhảy lên 1.0000, guardrail FAIL.
Lý do và cách xử lý nằm ở mục 06 failure case 3 — đó là một lỗi thật, không phải nhiễu.

Đọc bảng này cho đúng: engine trùng khớp hoàn toàn với gold nội bộ, nhưng gold đó do chính nhóm viết, nên
1.0000 chỉ nói "nhất quán", không nói "đúng". Phần đáng tin là baseline bỏ sót 3 case rủi ro còn PoC không bỏ
sót case nào, và lý do bỏ sót thì nhìn thấy được từng case ở mục 06.

Baseline B (hold-all) đạt Critical-miss 0.0000 nhưng False HOLD 1.0000 nên guardrail FAIL, Exact accuracy
0.8750. Nó cho thấy nếu chỉ đọc primary metric thì một cổng chặn sạch mọi thứ sẽ "thắng" cả PoC.

## 05 · Evaluation protocol

- Công thức, đơn vị, numerator và denominator, slices, cách báo khi N nhỏ: `reports/metric_contract.md`.
- Ngưỡng duy nhất (`retention.max_days = 365`) và toàn bộ rule file chốt ngày 2026-11-14, trước mọi lần
  evaluate. sha256 của file được ghi vào `run_info.json` và `decision.json` của từng run nên đối chiếu được sau.
- Số chính thức phải do giảng viên chạy. Lệnh evaluate của nhóm, chấm trên gold nội bộ:

```bash
python -m src.evaluate --track t09 --gt reports/internal_gold_dev.csv \
    --pred out/poc/decisions.csv --split all --run-name poc_reviewed \
    --out reports/metrics_poc_reviewed_internal.json
```

- Repo học viên không có `fixtures/t09_privacy_gate/gt/`: chạy `src.evaluate` mà không kèm `--gt` trả về
  **exit code 2** cùng thông báo thiếu ground truth. Nhóm đã chạy thử để kiểm, không chỉ đọc tài liệu.
- Độ bất định: N = 4 ở eval và N = 8 ở dev, nên mục 06 báo từng case chứ không chỉ báo tỷ lệ.

## 06 · Result slices

Chỉ 8 case dev có gold nội bộ, nên bảng dưới chỉ chấm trên 8 case đó. CASE-09 đến CASE-12 thuộc split eval,
repo học viên không có gold cho chúng, vì vậy nhóm **không** báo con số đúng/sai cho phần eval: quyết định của
hệ thống cho 4 case đó nằm trong `out/poc/decisions.csv` để giảng viên tự chấm.

| Slice (8 case dev) | N | Baseline A | PoC sau review | PoC engine-only | Ghi chú |
|---|---|---|---|---|---|
| VN (CASE-01, 03, 07) | 3 | 1 đúng | 3 đúng | 3 đúng | baseline cho GO cả CASE-03 và CASE-07 |
| EU (CASE-02, 04, 08) | 3 | 2 đúng | 3 đúng | 3 đúng | baseline cho GO CASE-02 |
| US-CA (CASE-05) | 1 | 1 đúng | 1 đúng | 1 đúng | cả hai đều chặn vì thiếu notice |
| SG (CASE-06) | 1 | 0 đúng | 1 đúng | 1 đúng | ở vòng duyệt đầu là 0 đúng, xem failure case 3 |
| gold = GO (chỉ CASE-06) | 1 | 0/1 | 1/1 | 1/1 | dev chỉ có một case GO nên false-HOLD rate chỉ nhận 0 hoặc 1 |
| gold = HOLD | 7 | 4/7 | 7/7 | 7/7 | baseline bỏ sót CASE-02, CASE-03, CASE-07 |

Bảng này được tính lại bằng một script độc lập đọc trực tiếp bốn file `decisions.csv` và gold nội bộ, không
lấy lại số từ evaluator. Lần tính lại đó bắt được hai lỗi trong bản nháp trước của báo cáo: bản nháp xếp
CASE-09 đến CASE-12 vào các slice theo thị trường như thể chúng có gold, và ghi VN là 2/4 đúng cho baseline
trong khi số thật là 1/3.

**Failure case 1 — CASE-02 (EU), baseline cho GO.** Consent đầy đủ cả bốn trường nên checklist consent kết
luận là hợp lệ. Nhưng `transfer.cross_border = true`, đích là "non-adequate third country", `mechanism = null`.
Consent là căn cứ *xử lý*, không phải cơ chế *chuyển* dữ liệu ra ngoài EEA: hai nghĩa vụ khác nhau, nằm ở hai
chương khác nhau của GDPR. Rule R-XB-01 bắn, HOLD với `XBORDER_NO_MECHANISM`. Đây đúng là failure mode mà
mục 5 của đề bài yêu cầu phân tích.

**Failure case 2 — CASE-03 (VN), baseline cho GO.** Có consent, nhưng consent gộp và không rút lại được
(`granular = false`, `withdrawable = false`), `retention_days = null`, và nặng nhất là `data_types` có `face`
trong khi `storage.raw_retained = true`, `location = cloud`, `anonymization = none`. Tức là mặt người được
giữ thô trên cloud, trong khi thiết kế được mô tả là "blur ở edge trước khi upload": chính cái kiểm soát mà
hồ sơ dựa vào thì không tồn tại. Ba rule bắn: CONSENT_INVALID (REWORK), RETENTION_UNBOUNDED (REWORK),
RAW_PII_IN_CLOUD (HOLD), theo thứ tự ưu tiên thành HOLD.

**Failure case 3 — CASE-06 (SG): một trường dữ liệu không rule nào đọc, và một người duyệt override sai vì
không nhìn thấy nó.** Đây là failure case đáng giá nhất của bài này, và nó do một reviewer ngoài nhóm chỉ ra.

Diễn biến theo đúng thứ tự:

1. Policy `g07-1.0.0` không có rule lawful basis nào cho thị trường SG. Engine cho CASE-06 là GO, nhưng là GO
   vì *không có rule nào bắn*, không phải vì hồ sơ có bằng chứng.
2. Người phụ trách escalate CASE-06 lên HOLD, ghi lý do: PDPA legitimate interests exception đòi một bản
   assessment mà hồ sơ không có.
3. Nhận định đó **sai sự thật**. `CASE-06.json` có `"li_assessment_done": true`. Hàng đợi review không hiển
   thị trường này, vì không rule nào đọc nó, nên người duyệt không có cách nào thấy.
4. Nguyên nhân sâu hơn: cùng một dữ kiện được fixture đặt hai tên khác nhau — CASE-06 dùng
   `li_assessment_done`, CASE-10 dùng `lia_done`. Policy v1.0.0 không đọc tên nào cả.
5. Kiểm tra hệ thống sau đó: nhóm liệt kê **toàn bộ** trường có trong 12 case rồi đối chiếu với toàn bộ trường
   mà rule đọc. Ngoài hai tên trên, chỉ còn `purpose`, `data_subjects` và `transfer.destination` là không được
   đọc, và cả ba đều không mang thông tin quyết định (ví dụ `data_subjects` giống nhau ở cả 12 case). Lỗi dừng
   ở một chỗ, không lan ra.
6. Cách sửa, phát hành thành `g07-1.1.0`: khai báo `field_aliases` ngay trong file rule (alias là dữ liệu có
   version, không phải bản vá trong code), thêm `R-SG-02` và `R-EU-04` yêu cầu bản assessment cho căn cứ lợi
   ích hợp pháp. Mỗi lần engine đổi tên trường, việc đó được ghi vào `audit_log.jsonl` và vào cột
   `field_normalisations` của `decisions.csv`, nên hàng đợi review lần sau có hiển thị nó.
7. Người duyệt viết lại ghi chú CASE-06 thành `approve`, nói rõ rằng ghi chú vòng một là sai và vì sao. Audit
   log là append-only nên giữ cả hai: lần escalate, rồi lần sửa. Đó đúng là việc audit log tồn tại để làm.

Đo được bao nhiêu: trước khi sửa, bản PoC định nộp có false HOLD 1.0000 và guardrail FAIL, tức là **vòng duyệt
của con người đang làm kết quả xấu đi** so với engine. Sau khi sửa, false HOLD về 0.0000, guardrail PASS, exact
accuracy 1.0000, và quyết định của engine với của người duyệt trùng nhau ở cả 12 case.

Hai điều đáng rút ra, và chúng không giống nhau. Thứ nhất, người duyệt chỉ kiểm được những gì hệ thống cho họ
xem: một trường mà rule không đọc thì cũng không lên màn hình, nên "có người duyệt" không bù được cho một lỗ
hổng trong rule. Thứ hai, với N = 1 ở lớp GO của tập dev, một override sai đủ để lật guardrail từ PASS sang
FAIL — số nhỏ thì mỗi quyết định đều là một phần rất lớn của metric.

Về việc đổi policy sau khi đã thấy kết quả: đây là sửa **lỗi đọc dữ liệu**, không phải chỉnh ngưỡng cho số đẹp.
Nhóm đã đo tác động trên cả 12 case trước khi phát hành: không case nào đổi quyết định, CASE-04 thêm mã
`LIA_MISSING` bên cạnh HOLD vốn đã có, CASE-06 vẫn GO nhưng từ nay có lý do, và **cả bốn case eval (CASE-09…12)
giữ nguyên quyết định**. Changelog nằm ngay đầu file rule, ghi cả phần nhóm đã bỏ sót ở v1.0.0.

**Ranh giới HOLD so với REWORK, và hai case nhóm biết là có thể đọc cách khác.** Tiêu chí của nhóm không phải
"lỗi nặng hay nhẹ" mà là **ai phải ra tay**: REWORK khi đội dữ liệu tự sửa được rồi nộp lại (đặt retention, thu
lại consent cho đúng, lấy bản ghi consent, giới hạn mục đích dùng SPI); HOLD khi phải có luật sư quyết hoặc
phải có hồ sơ nộp cơ quan (căn cứ pháp lý, cơ chế chuyển dữ liệu, DPIA, nội dung notice cho một thị trường
mới, dữ liệu nhận dạng được đã nằm trên cloud).

Theo tiêu chí đó, CASE-03 và CASE-05 là HOLD. Một reviewer khác chấm hai case này là REWORK, và đó là **khác
cách hiểu luật, không phải lỗi tính toán**. Lập luận của họ: thiếu notice hoặc dữ liệu lưu sai đều là thứ sửa
được trước khi bắt đầu thu, nên REWORK. Lập luận của nhóm: với CASE-05, nội dung notice theo CCPA là văn bản
pháp lý nên phải qua legal; với CASE-03, mặt người đã nằm thô trên cloud rồi, nên câu hỏi thật sự là xử lý
phần dữ liệu đã thu, và đó là quyết định của legal chứ không phải một lần sửa config. Nhóm giữ HOLD và ghi rõ
lựa chọn ở đây để người chấm thấy nó là một quyết định có lý do.

Chỗ này **không ảnh hưởng primary metric**: cả HOLD và REWORK đều được tính là "không GO", nên critical-miss và
false-HOLD rate không đổi dù chọn hướng nào. Nó chỉ ảnh hưởng exact decision accuracy, là chỉ số phụ. Bốn case
eval cho ra cùng quyết định ở cả hai bài: CASE-09 HOLD, CASE-10 GO, CASE-11 HOLD, CASE-12 HOLD.

Latency và compute: Windows 11 build 26300, Python 3.13.2, Intel i7-13620H, chỉ dùng CPU. PoC 0.1786 s cho
12 case tức khoảng 15 ms một case; baseline 0.0247 s. Không GPU, không gọi mạng.

## 07 · Human & decision

- **Review queue:** `out/poc/review_queue.csv`, B = 12, xếp theo `score` giảm dần. Score cộng từ mức nặng của
  rule đã bắn (HOLD 1.0, REWORK 0.5, NOTE 0.1), cộng 0.25 cho mỗi rule `needs_legal_review` và 0.10 cho mỗi
  rule `confidence: low`. Nghĩa là case vừa nhiều lỗi vừa dựa trên suy luận yếu thì lên đầu hàng đợi. Cao
  nhất là CASE-12 với 3.0, thấp nhất là CASE-06 và CASE-10 với 0.0. `out/poc/contact_sheet.html` là bản xem
  offline có dropdown quyết định và nút Export CSV.
- **Override và audit:** người phụ trách điền `reviewer`, `reviewer_decision` (`approve`, `reject`, `edit`,
  `escalate`, `skip`), `override_value`, `review_note`, lưu thành `out/poc/review_queue_reviewed.csv`, rồi
  chạy lại đúng một lệnh. Vòng này: 8 trong 12 case có quyết định, 1 case bị đổi (CASE-06 từ GO sang HOLD).
  Mỗi dòng ghi vào `out/poc/audit_log.jsonl` dạng append-only với ts, actor, action, before, after, reason.
  Dòng nào có quyết định mà trống `reviewer` thì `load_review_decisions` raise, không nhận quyết định vô
  danh. `edit` hoặc `reject` mà thiếu `override_value` cũng raise.
- **Decision policy:** `out/poc/decision.json` ghi status HOLD, reason_code `CASES_BLOCKED`, owner
  "Pham Huu Minh (data governance reviewer, G07)", kèm `policy_version`, `policy_sha256` và danh sách evidence
  trỏ tới decisions.csv, findings.csv, audit_checklist.md và rule file.
- **Khi nào HOLD hoặc REWORK thay vì tự động release:** mọi case có `ambiguity_notes` không rỗng đều HOLD,
  trừ ghi chú chỉ nói về ngày hiệu lực tương lai. Thị trường ngoài `covered_markets` cũng HOLD, vì một thị
  trường policy chưa phủ là rủi ro chưa biết, không phải rủi ro bằng không. Cổng này không bao giờ tự
  release: `audit_checklist.md` kết thúc bằng ba dòng ký mà người phụ trách phải tự tick.

## 08 · Reproduce & tests

```bash
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m tools.verify_manifests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main --track t09 --pipeline src.baselines.consent_only --output out/baseline --run-name baseline --offline --seed 42
.\.venv\Scripts\python.exe -m src.main --config configs/lab.yaml --track t09 --output out/poc --run-name poc --offline --seed 42
```

- `python -m tools.verify_manifests`: `14 manifests, 0 failing`.
- `python -m tools.field_coverage`: **exit 0**, mọi trường trong 12 case đều hoặc được rule đọc, hoặc khai
  trong `field_aliases`, hoặc khai trong `fields_not_used` kèm lý do. Kiểm ngược: bỏ hai khai báo đó ra khỏi
  một bản copy của file rule thì gate trả exit 1 và chỉ đúng `li_assessment_done` — tức là nó thật sự kiểm,
  không chỉ in ra chữ OK.
- `pytest -q`: **66 passed, 39 skipped, 0 failed**. 39 skip là các test cần GT của giảng viên, chúng tự skip.
  Trong đó 19 test của nhóm ở `tests/test_policy_engine.py` (một test chạy luôn gate ở trên): 13 test đường đúng (case EU sạch ra GO, cả 12 case
  fixture đều có quyết định kèm reason code, cross-border thiếu cơ chế thì HOLD, HOLD thắng REWORK, nghĩa vụ
  tương lai là NOTE rồi thành HOLD sau ngày hiệu lực, ambiguity escalate, thị trường ngoài phạm vi escalate,
  đọc field lồng nhau, retention null không làm sập rule số học, căn cứ lợi ích hợp pháp thiếu assessment thì
  HOLD, tên trường kiểu `li_assessment_done` vẫn được nhận, và giá trị `lia_done` tường minh thắng alias)
  và 6 test đường sai (rule thiếu source, operator lạ, trùng id, policy thiếu version, rule không có điều kiện,
  ngày sai định dạng).
- Ba test đường đúng đã **fail đúng lúc cần fail** khi policy lên v1.1.0: case mẫu trong test là EU dùng lợi
  ích hợp pháp mà chưa có `lia_done`, nên rule mới chặn nó. Nhóm sửa case mẫu cho đúng định nghĩa "sạch" mới
  chứ không nới rule.
- Hai guard đã kiểm bằng tay chứ không chỉ đọc tài liệu: GT guard chặn khi mở
  `fixtures/t09_privacy_gate/gt/gold_decisions.csv` (`GroundTruthAccessError`), offline guard chặn
  `socket.create_connection` ra ngoài (`NetworkBlockedError`).
- Máy: Windows 11 build 26300, Intel i7-13620H, Python 3.13.2. Git sha template `b0ce8bf`; config hash
  `8d2ab17cc02e` cho PoC và `7f4ab3c349ad` cho baseline.
- **Lưu ý khi chạy trên Windows:** `src/evaluate.py` in ký tự lớn-hơn-hoặc-bằng, console cp1252 không encode
  được nên lệnh evaluate chết với `UnicodeEncodeError` ngay sau khi đã tính xong metric. Đặt
  `PYTHONIOENCODING=utf-8` trước khi chạy. Nhóm không sửa code hạ tầng của lab vì giảng viên sẽ chạy lại bản gốc.

## 09 · Limitations & ethics

- **Không tuyên bố hệ thống này "đạt GDPR" hay "đạt Luật 91/2025".** Nó là công cụ rà soát: nó chỉ ra chỗ
  thiếu bằng chứng trong hồ sơ, theo một rule file do nhóm viết trong một buổi lab. Quyết định cuối thuộc
  DPO hoặc legal. 10 trong 12 case mang cờ `needs_legal_review`.
- Số điều luật trong rule file lấy từ bản dịch, chưa đối chiếu công báo. Rule EU về in-cabin video là diễn
  giải guideline EDPB nên `confidence: low`. Rule SG và rule SPI của California cũng `confidence: low`.
- **Không rule nào bắn không có nghĩa là hợp pháp.** CASE-06 ở v1.0.0 là ví dụ sống: policy không phủ lawful
  basis của SG nên case đó sạch dưới mắt engine, và cái "sạch" đó không dựa trên bằng chứng nào. Vì vậy
  `audit_checklist.md` in thẳng câu "an absent finding is not a legal clearance" ở mỗi case không có finding.
  Cùng lý do đó, phép đối chiếu "mọi trường trong dữ liệu so với mọi trường rule đọc" nên được chạy lại mỗi
  khi fixture hoặc rule file thay đổi; nó là thứ duy nhất bắt được loại lỗi này mà không cần người ngoài chỉ ra.
- Gold nội bộ không độc lập với rule file vì cùng một người suy ra, nên mọi con số dev chỉ là tự kiểm.
- Nếu số case tăng 10 lần: rule engine chạy tuyến tính nên không phải vấn đề, 8,8 ms một case. Nhưng số case
  cần người đọc cũng tăng tuyến tính và B = 12 không còn khả thi. Lúc đó phải xếp hàng theo risk score và
  chấp nhận rằng phần đuôi không có người xem, và đó chính là chỗ critical miss sẽ xuất hiện.
- Dữ liệu trong lab là synthetic, không có người thật. Khi áp lên dữ liệu thật thì bản thân hồ sơ case (thu ở
  đâu, thu của ai) cũng là dữ liệu cần bảo vệ.
- Kế hoạch v1.1: thêm R-SG-02 yêu cầu bằng chứng legitimate interests assessment cho SG; tách
  `NO_LAWFUL_BASIS` thành hai mã riêng cho "không có căn cứ" và "căn cứ không dùng được ở thị trường này";
  thêm nghĩa vụ xoá theo yêu cầu để nối với T08; đối chiếu số điều với công báo.

## 10 · Team contribution

**Bảng 2 · Individual contribution evidence**, đối chiếu `git shortlog -sne --all` sau khi commit:

| Học viên | Git author/email | Module / vai trò | Commit SHA / diff chứng minh | Trình bày? |
|---|---|---|---|---|
| 1. Nguyễn Hữu Thịnh | `nguyenhuuthinh.tabu@gmail.com` | Lead / Integrator — `.gitattributes`, `configs/lab.yaml`, nối dây 5 bước trong `src/pipeline.py`, hợp đồng one-command, đóng tag | ____ | |
| 2. Đinh Hữu Thái An | `dinhhuuthaian9191@gmail.com` | Policy & legal research — `configs/policy/privacy_policy_v1.yaml`: 21 rule, số điều, `source`, `version_date`, `confidence`, `needs_legal_review`, `field_aliases`, `fields_not_used` | ____ | |
| 3. Nguyễn Minh Triết | `benny.nee0512@gmail.com` | Core algorithm — `src/policy/engine.py`: rule DSL không dùng `eval()`, precedence HOLD > REWORK > GO, hạ rule chưa hiệu lực xuống NOTE, áp field alias và báo lại cho audit log | ____ | |
| 4. Phạm Thị Lương | `26ai.luongpt@vinuni.edu.vn` | Baseline & metric — `src/baselines/consent_only.py`, `src/baselines/hold_all.py`, chạy `src.evaluate` và `src.compare`, `reports/metrics_*_internal.json`, hai bảng so sánh | ____ | |
| 5. Đoàn Thị Ánh Hậu | `26ai.haudta@vinuni.edu.vn` | QA & test — `tests/test_policy_engine.py` (19 test), `tools/field_coverage.py`, `reports/internal_gold_dev.csv`, kiểm `manifest.csv`, kiểm GT guard và offline guard, kiểm hai run cho ra kết quả giống nhau | ____ | |
| 6. Phạm Hữu Minh | ____ | Human review & report — vòng review 8/12 case, `audit_checklist.md`, `reports/group_report.md`, `reports/metric_contract.md`, `demo/README.md`; là người ký duyệt trong `decision.json` và `audit_log.jsonl` | ____ | có |

Cột commit để trống vì chưa ai commit. Ba điều cần làm trước khi nộp:

1. Mỗi người đặt `git config user.name` và `user.email` **đúng y như** hai cột trên, nếu không
   `git shortlog -sne --all` sẽ không gom đúng người. Phạm Hữu Minh tự điền email git của mình vào bảng.
2. Quy tắc 6 của lab: mỗi người cần **ít nhất một commit thực chất** vào đúng file của mình; commit chỉ đổi
   khoảng trắng không được tính. Việc đã chia theo ranh giới file nên không ai phải sửa file của người khác,
   và thứ tự push nằm trong `UPLOAD_PLAN.md`.
3. Người ký duyệt hiện là Phạm Hữu Minh, tên này đã nằm trong `decision.json`, `audit_log.jsonl` và
   `audit_checklist.md`. Nếu nhóm đổi người ký, sửa `owner` trong `configs/lab.yaml` rồi chạy lại một lệnh
   PoC để audit trail mang đúng tên.

`reports/team_contributions.csv` có đúng sáu dòng khớp với bảng trên. Commit gốc `b0ce8bf` là của template do
giảng viên phát (tác giả `loversky02`), không tính cho thành viên nào.

## 11 · References

| URL | Ngày xem | Ý nghĩa |
|---|---|---|
| https://thuvienphapluat.vn/van-ban/Bo-may-hanh-chinh/Luat-Bao-ve-du-lieu-ca-nhan-2025-so-91-2025-QH15-625628.aspx | 2026-11-13 | VN chỉ cho xử lý dựa trên đồng ý hoặc các trường hợp miễn đồng ý được liệt kê, và có nghĩa vụ hồ sơ đánh giá tác động |
| https://eur-lex.europa.eu/eli/reg/2016/679/oj | 2026-11-14 | Căn cứ xử lý, điều kiện consent, giới hạn lưu trữ, bảo mật, DPIA, và một chương riêng cho chuyển dữ liệu ra ngoài EEA |
| https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=1798.100&lawCode=CIV | 2026-11-14 | California siết thông báo tại thời điểm thu, không dùng khái niệm lawful basis |
| https://www.edpb.europa.eu/our-work-tools/our-documents/guidelines/guidelines-012020-processing-personal-data-context_en | 2026-11-14 | Xe kết nối: xử lý trong khoang xe với người nhận dạng được cần căn cứ chặt hơn và balancing test |
| https://www.meity.gov.in/data-protection-framework | 2026-11-14 | DPDP và bộ Rules 2025: mốc hiệu lực các nghĩa vụ cốt lõi, đồng ý của cha mẹ cho trẻ em |
| https://sso.agc.gov.sg/Act/PDPA2012 | 2026-11-14 | PDPA mục 26: chuyển dữ liệu ra ngoài Singapore phải bảo đảm mức bảo vệ tương đương |

---

**Bảng 3 · Checklist chốt khi nộp**

- [ ] Link repo và tag cuối cùng trong README; input mẫu không chứa PII thật.
- [x] Đúng 1 lệnh run, 1 lệnh evaluate, 1 lệnh tests; không cần download khi chạy.
- [x] Có baseline và PoC metrics, 3 failure case, reviewer evidence, decision log.
- [x] Có license và source provenance, data splits, seed, offline environment, GT/eval N.
- [ ] Mỗi thành viên có ít nhất 1 commit thực chất và được nêu minh bạch trong bảng trên.
