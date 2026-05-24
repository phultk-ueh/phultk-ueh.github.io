# Mô tả dữ liệu và Mapping

> Tất cả file dưới đây có link mở xem trực tiếp trên Google Sheets.
> **Truy cập bằng email UEH** (`@ueh.edu.vn`) để được cấp quyền xem.

## 1. Tổng quan dữ liệu đầu vào

| STT | File | Mô tả | Đơn vị cung cấp | Sheet | Header row | Sheet đầu ra | Tình trạng | Ghi chú |
|---:|---|---|---|---|---:|---|---|---|
| 1 | [01-quymo-sinhvien-dh.xlsx](https://docs.google.com/spreadsheets/d/1MxWTw5P7nJgzSitpRNLsvx_FicWwg-Ll) | Quy mô sinh viên đại học (ĐHCQ, VLVH, CTLK) | Ban Đào tạo | Sheet1 | 3 | Quy mô sinh viên | Dùng | |
| 2 | [02-hocphan-sotiet-2025.xlsx](https://docs.google.com/spreadsheets/d/1FHYNQ8oRCdrKDCysOhZ2bXCe94gBapF3) | Học phần & số tiết 2025 | Ban Đào tạo | Sheet 1 | 1 | Phụ lục 2. DS môn học 2025 | Dùng | Chưa có phân Khoa — ghép với file 03 theo Mã HP. |
| 3 | [03-monhoc-khoa-phutrach.xlsx](https://docs.google.com/spreadsheets/d/1pDzKk2ftQrFUHEio8mndekQKaK4i6R-z) | Mã HP → Khoa phụ trách | Ban Đào tạo | Sheet1 | 1 | Phụ lục 2. DS môn học 2025 | Dùng | Có sẵn tên canonical "PREFIX - Khoa…". Cũng là nguồn tên đơn vị chuẩn hoá. |
| 4 | [04-ctdt-co-phankhoa.xlsx](https://docs.google.com/spreadsheets/d/1jKE-MoFYLjr0H_epBwUjzhqoL_EAvg7I) | CTĐT có phân Khoa (146 CT) | Ban Bảo đảm chất lượng - Phát triển chương trình | Chuongtrinhdaotao | 1 | Chuongtrinhdaotao | Dùng | Mã CT khác với của Sau Đại học. Khoa/Viện có sẵn tên prefix. |
| 5 | [05-ctdt-khong-phankhoa.xlsx](https://docs.google.com/spreadsheets/d/1JF_eqe1AmCjVcjgvSj1ilr9a5b32GIIu) | CTĐT không phân Khoa (mẫu Bộ) | Ban Sau Đại học | CTDT | 2 | — | Tham khảo | Dữ liệu CTĐT đã có đầy đủ trong file 04. |
| 6 | [06-hocvien-ncs-sdh.xlsx](https://docs.google.com/spreadsheets/d/1mxKAiuqKtrRxJ8OPVz7hmYRpY95Y38_F) | Học viên Cao học & NCS (~9.600 dòng) | Ban Sau Đại học | HT_NCS | 2 | Quy mô SĐH | Dùng | Đếm 'Đang học' theo mã ngành (7 ký tự đầu); leading 8 = ThS, 9 = TS. |
| 7 | [07-quymo-nhansu-gv.xlsx](https://docs.google.com/spreadsheets/d/1xJLOvv9p0rhpSK82YnJ0iMUhymonDZ0g) | Danh sách nhân sự — quy mô GV (1.070 dòng) | Ban Phát triển Tổ chức - Nhân lực | Danhsach | 1 | Quy mô giảng viên | Dùng | Lọc Chức danh chứa "Giảng viên" hoặc "isb". NCS toàn thời gian được giữ (Nhóm 5). |
| 8 | [08-donvi-giangday.xlsx](https://docs.google.com/spreadsheets/d/1E5ZWNO7rbG-lBSbMe0wnxrK9lBTxvv4j) | Mã quản lý → Đơn vị giảng dạy (949 mapping) | Ban Phát triển Tổ chức - Nhân lực | Sheet1 | 1 | Đơn vị giảng dạy | Dùng | Mapping GV Nhóm 4. |

---

## 2. Dữ liệu đầu ra

[Duthaokehoach_merged.xlsx](https://docs.google.com/spreadsheets/d/15OI6vvNjn-ci4aEHkJbAEzA5f6l09WV5) chứa 6 sheet đã được gộp & chuẩn hoá:

| Sheet | Nguồn |
|---|---|
| Quy mô giảng viên | 07 |
| Phụ lục 2. DS môn học 2025 | 02 + 03 |
| Quy mô sinh viên | 01 |
| Quy mô SĐH | 06 + 04 |
| Đơn vị giảng dạy | 08 |
| Chuongtrinhdaotao | 04 |

---

## 3. Xử lý dữ liệu

### 3.1. Mapping chi tiết từng file

#### `01-quymo-sinhvien-dh.xlsx` → sheet **Quy mô sinh viên**

| Cột nguồn | Cột đích | Phép biến đổi |
|---|---|---|
| Tên chương trình đào tạo | Tên chương trình đào tạo | Sao chép trực tiếp |
| Khoa/Viện quản lý | Khoa/Viện quản lý | Chuẩn hoá về tên canonical (`PREFIX - Khoa…`) |
| ISB-CQ, Chính quy, VB2 CQ, Liên thông CQ, VB1 VLVH, VB2 VLVH, Liên thông CĐ VLVH, Liên thông TC VLVH, CỘNG | 9 cột số liệu sinh viên | Parse số (mặc định 0) |
| — | tong ĐHCQ, VLVH | Tính trong pipeline: Σ 4 cột CQ-related; Σ 4 cột VLVH-related |

**Lưu ý:** bỏ dòng cuối `CỘNG` của file nguồn để tránh tính trùng tổng.

#### `02-hocphan-sotiet-2025.xlsx` + `03-monhoc-khoa-phutrach.xlsx` → sheet **Phụ lục 2. DS môn học 2025**

| Cột nguồn (file) | Cột đích | Phép biến đổi |
|---|---|---|
| `02`: Mã HP, Tên HP, Bậc đào tạo, Số LHP, Số tín chỉ, Tổng số tiết | 6 cột tương ứng | Sao chép + parse số |
| `03`: Khoa (lookup theo Mã HP) | Đơn vị phụ trách | Join với 02 trên `Mã HP`. File 03 đã có tên canonical sẵn. |
| (suy luận) | Ghi chú | Tự gắn `"Tính định biên"` nếu Đơn vị là Khoa / Viện / Trung tâm / Phòng dạy học; trừ admin (Ban GH, Văn phòng, Phòng Chăm sóc). |

#### `04-ctdt-co-phankhoa.xlsx` → sheet **Chuongtrinhdaotao**

| Cột nguồn | Cột đích | Phép biến đổi |
|---|---|---|
| Stt, Mã chương trình, Tên chương trình, Mã ngành, Tên ngành, Lĩnh vực, Trường thành viên, Khoa/Viện, Năm tuyển sinh, Trình độ, Loại hình, Hình thức đào tạo | 13 cột tương ứng | Sao chép; Khoa/Viện chuẩn hoá về canonical |

#### `06-hocvien-ncs-sdh.xlsx` + `04-ctdt-co-phankhoa.xlsx` → sheet **Quy mô SĐH**

| Cột nguồn (HT_NCS) | Cột đích | Phép biến đổi |
|---|---|---|
| Mã chương trình đào tạo | Mã_Ngành_ThS, Mã_Ngành_TS | Lấy **7 ký tự đầu** = Mã ngành đào tạo. Leading: `7` = ĐH, `8` = ThS, `9` = TS. |
| Trạng thái học | (bộ lọc) | Chỉ giữ "Đang học" để đếm quy mô hiện hành. |
| (count) | Quy_mô_ThS, Quy_mô_TS | Đếm số học viên đang học theo (mã ngành × trình độ). |
| (join với 04 theo mã ngành) | Đơn vị quản lý, Ngành, Số chương trình | Lấy Tên ngành + Khoa/Viện đại diện. |

#### `07-quymo-nhansu-gv.xlsx` → sheet **Quy mô giảng viên**

| Cột nguồn | Cột đích | Phép biến đổi |
|---|---|---|
| 22 cột chuẩn (Mã quản lý, Họ tên, … Tình trạng làm việc) | 22 cột tương ứng (giữ format 100%) | Parse số (Mã quản lý, CMND, Năm TN, ĐT); parse ngày (Ngày sinh); parse bool (Giới tính). Mã quản lý chuẩn hoá bỏ đuôi `.0` để join ổn định với 08. |

#### `08-donvi-giangday.xlsx` → sheet **Đơn vị giảng dạy**

| Cột nguồn | Cột đích | Phép biến đổi |
|---|---|---|
| STT | (bỏ) | Không xuất |
| Mã quản lý | Mã quản lý | Parse int. Khoá join với 07. |
| Đơn vị giảng dạy | Đơn vị giảng dạy | Sao chép trực tiếp |

### 3.2. Bảng tra tên đơn vị (canonical map)

Nhiều file nguồn có tên đơn vị ở dạng ngắn ("Khoa Kế toán"), trong khi format target dùng tên có prefix mã trường thành viên ("KD - Khoa Kế toán"). Pipeline quét file 03 và 08 để xây bảng tra:

| Tên không prefix (lowercase) | Tên canonical |
|---|---|
| khoa công nghệ thông tin kinh doanh | CNTK - Khoa Công nghệ thông tin kinh doanh |
| khoa thiết kế truyền thông | CNTK - Khoa Thiết kế Truyền thông |
| viện công nghệ thông minh và tương tác | CNTK - Viện Công nghệ thông minh và tương tác |
| viện đô thị thông minh và quản lý | CNTK - Viện Đô thị thông minh và quản lý |
| viện đổi mới sáng tạo | CNTK - Viện Đổi mới sáng tạo |
| khoa du lịch | KD - Khoa Du lịch |
| khoa kinh doanh quốc tế - marketing | KD - Khoa Kinh doanh quốc tế - Marketing |
| khoa kế toán | KD - Khoa Kế toán |
| khoa ngân hàng | KD - Khoa Ngân hàng |
| khoa quản trị | KD - Khoa Quản trị |
| khoa tài chính | KD - Khoa Tài chính |
| khoa kinh tế | KTLQLNN - Khoa Kinh tế |
| khoa luật | KTLQLNN - Khoa Luật |
| khoa ngoại ngữ | KTLQLNN - Khoa Ngoại ngữ |
| khoa quản lý nhà nước | KTLQLNN - Khoa Quản lý nhà nước |
| khoa toán - thống kê | KTLQLNN - Khoa Toán - Thống kê |
| khoa tài chính công | KTLQLNN - Khoa Tài chính công |
| viện tài chính bền vững | KTLQLNN - Viện Tài chính bền vững |
| khoa tài chính - ngân hàng | PHVL - Khoa Tài chính - Ngân hàng |
