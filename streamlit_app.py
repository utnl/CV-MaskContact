import streamlit as st
import fitz  # PyMuPDF
import re
from collections import Counter

st.set_page_config(page_title="CV Masking Pro", layout="wide")

def get_accurate_bg_color(page, rect):
    """
    Lấy mẫu màu nền thông minh: Tìm màu phổ biến nhất trong vùng lân cận 
    nhưng bỏ qua các màu quá tối (màu chữ/icon).
    """
    try:
        # Lấy mẫu một vùng bên cạnh chữ (cách 15px)
        sample_rect = fitz.Rect(rect.x0 - 40, rect.y0, rect.x0 - 10, rect.y1)
        if sample_rect.x0 < 0: # Nếu sát lề trái quá thì lấy bên phải
            sample_rect = fitz.Rect(rect.x1 + 10, rect.y0, rect.x1 + 40, rect.y1)
            
        pix = page.get_pixmap(clip=sample_rect)
        samples = pix.samples
        colors = []
        for i in range(0, len(samples), 3):
            r, g, b = samples[i], samples[i+1], samples[i+2]
            # Bỏ qua các pixel quá tối (tổng RGB < 150) vì khả năng cao là chữ hoặc icon
            if (r + g + b) > 150: 
                colors.append((r, g, b))
        
        if not colors: # Nếu không tìm được màu sáng, lấy màu phổ biến nhất bất kỳ
            for i in range(0, len(samples), 3):
                colors.append((samples[i], samples[i+1], samples[i+2]))

        most_common = Counter(colors).most_common(1)[0][0]
        return (most_common[0]/255, most_common[1]/255, most_common[2]/255)
    except:
        return (1, 1, 1) # Trắng mặc định

def process_cv_v5(input_bytes):
    doc = fitz.open(stream=input_bytes, filetype="pdf")
    
    EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    PHONE_REGEX = r'(?:\(?\+?84\)?|0(?:\d{1,2})?)\s*[\.\-\s]?\d(?:\s*[\.\-\s]?\d){7,11}'
    URL_KEYWORDS = ["linkedin.com", "facebook.com", "fb.com", "bit.ly", "tinyurl.com", "goo.gl"]

    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            # Lấy ranh giới bên phải của khối văn bản (giới hạn sidebar)
            block_right_limit = b["bbox"][2]
            
            if "lines" in b:
                for l in b["lines"]:
                    line_text = "".join([s["text"] for s in l["spans"]])
                    line_rect = fitz.Rect(l["bbox"])
                    
                    is_match = (re.search(EMAIL_REGEX, line_text) or 
                                re.search(PHONE_REGEX, line_text) or 
                                any(kw in line_text.lower() for kw in URL_KEYWORDS))

                    if is_match:
                        bg_color = get_accurate_bg_color(page, line_rect)
                        
                        # --- TỐI ƯU VÙNG CHE ---
                        # x0: Mở rộng trái 45px để đè icon
                        # x1: Chỉ mở rộng tối đa 5px so với chữ, HOẶC dừng lại ở mép block
                        new_x1 = min(line_rect.x1 + 5, block_right_limit + 2)
                        
                        mask_rect = fitz.Rect(
                            line_rect.x0 - 45, 
                            line_rect.y0 - 2, 
                            new_x1, 
                            line_rect.y1 + 2
                        )
                        page.add_redact_annot(mask_rect, fill=bg_color)
        
        # Tìm kiếm bổ sung (Fix lỗi loang lề ở đây)
        for kw in URL_KEYWORDS:
            for rect in page.search_for(kw):
                bg_color = get_accurate_bg_color(page, rect)
                # Chỉ mở rộng phải 5px thay vì 100px như trước
                page.add_redact_annot(rect + (-45, -2, 5, 2), fill=bg_color)

        page.apply_redactions()
    return doc
# --- GIAO DIỆN ---
st.title("🛡️ CV Redactor Pro V5")
st.write("Đã sửa lỗi bắt màu và thêm chặn link Bitly.")

uploaded_file = st.file_uploader("Tải lên PDF", type="pdf")

if uploaded_file:
    original_name = uploaded_file.name
    if st.button("🚀 Thực hiện che sạch"):
        with st.spinner('Đang xử lý màu sắc tiệp nền...'):
            processed_doc = process_cv_v5(uploaded_file.getvalue())
            
            st.success("Hoàn tất! Vết che đã tiệp màu nền.")
            col1, col2 = st.columns([2, 1])
            with col1:
                st.image(processed_doc[0].get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png"), use_container_width=True)
            with col2:
                st.download_button(
                    label=f"📥 Tải lại {original_name}",
                    data=processed_doc.tobytes(),
                    file_name=original_name,
                    mime="application/pdf"
                )
            processed_doc.close()