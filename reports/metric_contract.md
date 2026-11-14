# Metric contract (khai báo bắt buộc — chốt ở phút 30, trước khi chạy eval)

> Các metric chuẩn đã được cài trong `src/metrics/tracks.py`. File này là nơi nhóm **cam kết** cách dùng chúng.
> Không đổi testset, threshold hay trọng số sau khi đã thấy kết quả eval.

| Mục | Khai báo của nhóm |
|---|---|
| Track | T09 · Multi-Market Privacy Decision Gate |
| Primary metric (tên đúng như evaluator in ra) | `Critical-miss Rate` (tương đương `High-risk HOLD Recall`) |
| Tăng tốt hay giảm tốt? | lower |
| Đơn vị đánh giá (image / region / pair / release / batch / case …) | **case** — một hồ sơ thu dữ liệu cho một thị trường |
| Công thức + numerator / denominator | numerator = số case rủi ro (gold khác GO) bị hệ thống cho GO; denominator = tổng số case rủi ro trong split. Case thiếu trong `decisions.csv` bị tính là GO (worst case) |
| Cách ghép prediction ↔ GT (IoU? id? tolerance?) | join theo `case_id`, một dòng cho mỗi case, không trùng (hàm `_unique` trong evaluator sẽ chặn) |
| Candidate pool cố định | 12 case trong `fixtures/t09_privacy_gate/cases/`, không thêm không bớt, hash khớp `manifest.csv` |
| Review budget B / K | B = 12: mọi case đều ra màn hình người phê duyệt, không chỉ các case rủi ro nhất |
| Seed | 42 |
| Threshold policy (chọn trên dev như thế nào) | Rule file `configs/policy/privacy_policy_v1.yaml`, **chốt `g07-1.0.0` ngày 2026-11-14 trước khi chạy evaluate**. Ngưỡng số duy nhất là `retention.max_days = 365`, chọn bằng lập luận mục đích (ADAS training không cần giữ quá một năm video thô), không chỉnh theo kết quả. Bản nộp là `g07-1.1.0`, sha256 `ef49790a9ef3c744…`, 21 rule — chi tiết ở dòng dưới |
| Eval split (không dùng để tune) | `split: eval` = CASE-09…12 là số chính thức. CASE-01…08 là dev, nhóm được đọc kỹ. `--split all` chỉ dùng để tự kiểm |
| Chỉ số lỗi xấu (miss / false alarm / false reject) | **miss** = case rủi ro bị cho GO, nguy hiểm nhất vì dữ liệu đã thu xong mới phát hiện sai. **false HOLD** = case sạch bị chặn, đây là guardrail và phải ở mức 0,5 trở xuống, nếu không primary metric không còn giá trị |
| Slices sẽ báo cáo (≥2) | (1) theo thị trường VN / EU / US-CA / SG / IN; (2) theo `gold_decision` (GO so với HOLD và REWORK); (3) theo nhóm reason code (lawful basis, cross-border, retention và security, consent) |
| Cách báo độ bất định khi N nhỏ | N = 4 ở split eval, N = 8 ở dev, nên **báo từng case** chứ không chỉ báo tỷ lệ. Mỗi case chiếm 25% (eval) hoặc 12,5% (dev) của metric; ở dev chỉ có một case GO nên false-HOLD rate chỉ nhận giá trị 0 hoặc 1, phải nói rõ điều đó thay vì làm tròn |
| Ngày giờ chốt + người chốt | 2026-11-14, Phạm Hữu Minh (reviewer, người ký duyệt của G07) |

Nếu baseline = 0 thì ghi rõ "baseline = 0" thay vì phần trăm cải thiện.

## Vì sao policy đổi từ 1.0.0 sang 1.1.0 sau khi đã thấy kết quả

Quy tắc 1 của lab cấm tune sau khi nhìn kết quả, nên lần đổi này phải nói rõ nó là gì và không phải là gì.

Nó là **sửa lỗi đọc dữ liệu**: v1.0.0 không có rule nào đọc trường ghi nhận bản đánh giá lợi ích hợp pháp, mà
fixture lại đặt trường đó hai tên khác nhau (`li_assessment_done` ở CASE-06, `lia_done` ở CASE-10). Một reviewer
ngoài nhóm phát hiện. v1.1.0 thêm `field_aliases`, `R-SG-02` và `R-EU-04`.

Nó **không phải** chỉnh ngưỡng cho số đẹp, và đây là bằng chứng: tác động được đo trên cả 12 case trước khi phát
hành, không case nào đổi quyết định; CASE-04 thêm mã `LIA_MISSING` cạnh HOLD vốn đã có; CASE-06 vẫn GO nhưng từ
chỗ "không rule nào bắn" thành "có bằng chứng trong hồ sơ"; **cả bốn case eval CASE-09…12 giữ nguyên quyết
định**. Ngưỡng số duy nhất của policy (`retention.max_days = 365`) không đổi. Changelog đầy đủ nằm ở đầu file
rule, kèm câu thừa nhận nhóm đã bỏ sót trường đó ở v1.0.0.

## Hai baseline, chốt cùng lúc với policy

| Baseline | Module | Chính sách | Vì sao phải báo |
|---|---|---|---|
| A · consent-only | `src.baselines.consent_only` | có `consent.obtained` thì GO, còn lại HOLD | Đúng cái checklist mà handout gọi là sai: coi consent là đủ căn cứ |
| B · hold-all | `src.baselines.hold_all` | HOLD mọi case | Critical-miss bằng 0 nhưng guardrail FAIL, chứng minh primary metric không được đọc một mình |

## Giới hạn của phép tự kiểm nội bộ

Repo học viên không có `fixtures/t09_privacy_gate/gt/`, nên số chính thức phải do giảng viên chạy. Đã kiểm:
`python -m src.evaluate --track t09 --pred out/poc/decisions.csv` trả về exit code 2 kèm thông báo thiếu ground truth.

Nhóm tự gán nhãn 8 case dev vào `reports/internal_gold_dev.csv` để so baseline với PoC trên cùng một thước đo.
Nhãn đó do chính nhóm suy ra từ văn bản luật nên **không độc lập với rule file**. Hệ quả:

- con số tuyệt đối trên dev chỉ đo mức nhất quán nội bộ, không phải mức đúng;
- phần có ý nghĩa là khoảng cách giữa baseline và PoC, không phải trị số của PoC;
- mỗi nhãn đều có cột `basis_of_label` ghi căn cứ, để giảng viên bắt lỗi được từng dòng.
