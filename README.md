# App chuyển tone cảm âm Đô Rê Mi

App Streamlit giúp dán cảm âm dạng `do re mi fa sol la si`, rồi chuyển lên/xuống tone khác để dễ chơi đàn hơn.

## Cách chạy

```bash
pip install -r requirements.txt
streamlit run app.py
```

## App hiểu các kiểu ghi

- `do re mi fa sol la si`
- `fa#`, `sol#`, `do#`
- `si\`` là nốt thấp hơn
- `do2`, `re2`, `do2#` là nốt cao hơn

## Chế độ chính

1. Tự chọn số nấc lên/xuống.
2. Chọn tone gốc và tone muốn chơi.
3. App tự gợi ý tone dễ chơi, ưu tiên ít dấu `#`/`b` và không dịch quá xa.
