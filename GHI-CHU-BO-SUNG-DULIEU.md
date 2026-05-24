# Ghi chú nội bộ — Bổ sung dữ liệu

> File này chỉ dành cho người maintain. Không gửi cho end-user.

## Nguồn bổ sung
Lấy từ `Duthaokehoachtuyendung2026-2030.xlsx` (file thủ công, người làm trước đã rà soát hàng giờ liền).

## Các thay đổi đã thực hiện

### `04-ctdt-co-phankhoa.xlsx` (143 → 146 CT)

| # | Hành động | Mã CT | Tên CT | Khoa/Viện |
|---|---|---|---|---|
| 1 | Sửa khoa trống | `834020103VI06` | Quản lý tài sản (hướng nghiên cứu) | (trống) → **TN - Khoa Tài năng kinh doanh** |
| 2 | Thêm dòng mới | `831011003VI01` | Quản lý kinh tế (hướng ứng dụng) | Khoa Kinh tế |
| 3 | Thêm dòng mới | `831010503VI05` | Kinh tế học ứng dụng (Việt Nam - Hà Lan) | Khoa Kinh tế |
| 4 | Thêm dòng mới | `834010103VI04` | Quản trị công nghệ (hướng ứng dụng) | Viện Công nghệ thông minh và tương tác |

### `08-donvi-giangday.xlsx` (562 → 949 mapping)

- Thêm **387 dòng mapping** từ file gốc thủ công (Mã quản lý → Đơn vị giảng dạy cho các GV nhóm 4 chưa có trong 8.xlsx ban đầu).
- Sửa 3 mapping ISB:
  - `isb026` : 'TN - Khoa Tài năng kinh doanh' → **'KD - Khoa Kinh doanh quốc tế - Marketing'**
  - `isb040` : 'TN - Khoa Tài năng kinh doanh' → **'KTLQLNN - Khoa Ngoại ngữ'**
  - `isb023` : 'TN - Khoa Tài năng kinh doanh' → **'Ban Chăm sóc người học'**

### `07-quymo-nhansu-gv.xlsx` (1.070 dòng — không bổ sung)
File này đầy đủ hơn gốc (1.070 vs 953). 953 GV của gốc đều có trong file mới + 117 GV mới (tuyển/cập nhật sau). Giữ nguyên.

## Backup giữ trong `backup/`
- `04-ctdt-co-phankhoa_original_backup.xlsx`
- `07-quymo-nhansu-gv_original_backup.xlsx`
- `08-donvi-giangday_original_backup.xlsx`

Nếu cần rollback, copy đè vào `data/` với tên mới tương ứng.

## Đối chiếu với file gốc sau bổ sung

| Sheet | Gốc | Tôi | Trạng thái |
|---|--:|--:|---|
| Quy mô giảng viên | 953 | 1.070 | Gốc ⊂ Tôi (+117 GV mới) |
| Phụ lục 2 DS môn học | 1.637 | 1.637 | Khớp 100% (cả tổng tiết 402.667) |
| Quy mô sinh viên | 81 | 81 | Khớp 100% (CỘNG 31.927) |
| Quy mô SĐH (per-ngành) | 4.560 ThS + 417 TS | **Khớp 100%** | 16/16 ngành đúng từng số |
| Đơn vị giảng dạy | 953 | 948 | Còn lệch 5 mapping nhỏ |
| Chuongtrinhdaotao | 161 (có duplicate) | 146 (unique) | Tương đương về unique mã CT |

## Đề xuất nâng cấp pipeline trong tương lai

**3-layer mapping cho phân khoa SĐH chính xác hơn** (đã thiết kế & verify, **chưa implement**):

Hiện tại pipeline build sheet Quy mô SĐH ở mức per-ngành (16 ngành), sau đó `build_data` redistribute về khoa theo tỷ lệ số CT trong file 04. Cách này có thể bias (vd Viện Đổi mới sáng tạo nhận 168 HV dù thực tế 0 HV đăng ký).

Pipeline mới đề xuất (3 lớp) — đạt **100% học viên đang học được phân khoa chính xác** theo từng HV:

1. **Stage 1**: Mỗi HV trong file 06 có Mã CT đầy đủ → lookup file 05 (full Mã CT khớp 100%) để lấy **Tên CT + Loại CTĐT** (định hướng ứng dụng/nghiên cứu/TS).
2. **Stage 2**: Lookup file 04 qua 3 lớp:
   - L1 Exact: `(Mã ngành 7 số + Tên CT normalize + Hướng)` → 98,4%.
   - L2 Fuzzy + cùng hướng (sim ≥ 0.55): bắt "Quản lý" ↔ "Quản trị" → +1,4%.
   - L3 Fuzzy bất kể hướng (sim ≥ 0.55) → +0,2%.
3. **Stage 3 (fallback)**: chia theo tỷ lệ số CT (logic hiện tại) cho các edge case.

**Để implement**: cần sửa `pipeline.py::build_pg` (sử dụng cả 05) và `build_data.py::transform_data` (thay phần CTDT redistribute SĐH).

Đã verify: per-ngành 100% khớp file gốc (4.560 ThS + 417 TS), per-khoa khác gốc vì gốc cũng dùng CTDT redistribute (cùng bias).

## Cảnh báo cho lần update sau

1. Nếu nhận file `04` mới từ Ban BĐCL: kiểm tra xem 4 dòng đã bổ sung ở trên có nằm trong file mới chưa. Nếu chưa → bổ sung lại (hoặc yêu cầu Ban BĐCL cập nhật vào source).
2. Nếu nhận file `08` mới từ Ban PT Tổ chức - Nhân lực: kiểm tra xem có đầy đủ 949+ mapping chưa. Nếu chỉ ~562 → phải bổ sung lại từ file gốc.
3. File `05-ctdt-khong-phankhoa.xlsx` (Ban SĐH): rất quan trọng — chứa cột `Loại CTĐT` phân biệt hướng đào tạo. Không được bỏ.
