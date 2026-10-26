import streamlit_app as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dashboard Doanh Số E-Commerce", page_icon="📊", layout="wide")

conn = st.connection("mysql", type="sql")

SALES_SQL = """
SELECT
    o.order_id,
    o.order_date,
    o.order_status,
    cu.customer_name,
    cu.customer_city,
    c.category_name,
    p.product_name,
    od.order_quantity,
    od.unit_price,
    od.order_quantity * od.unit_price AS line_revenue
FROM Orders o
JOIN Customers cu    ON cu.customer_id = o.customer_id
JOIN OrderDetails od ON od.order_id    = o.order_id
JOIN Products p      ON p.product_id   = od.product_id
JOIN Categories c    ON c.category_id  = p.category_id
ORDER BY o.order_date, o.order_id
"""

DETAIL_COLUMNS = {
    "order_id": "Mã Đơn",
    "order_date": "Ngày Đặt",
    "order_status": "Trạng Thái",
    "customer_name": "Khách Hàng",
    "customer_city": "Thành Phố",
    "category_name": "Danh Mục",
    "product_name": "Sản Phẩm",
    "order_quantity": "Số Lượng",
    "unit_price": "Đơn Giá",
    "line_revenue": "Thành Tiền",
}

try:
    sales = conn.query(SALES_SQL, ttl=600)
except Exception as e:
    st.error(f"Không thể kết nối CSDL: {e}")
    st.stop()

if sales.empty:
    st.warning("CSDL chưa có đơn hàng nào!")
    st.stop()

sales["order_date"] = pd.to_datetime(sales["order_date"])
min_date = sales["order_date"].min().date()
max_date = sales["order_date"].max().date()

st.sidebar.header("🔍 Bộ Lọc Dữ Liệu")

start = st.sidebar.date_input("Từ ngày:", min_date, min_value=min_date, max_value=max_date)
end = st.sidebar.date_input("Đến ngày:", max_date, min_value=min_date, max_value=max_date)

all_statuses = sorted(sales["order_status"].unique())
statuses = st.sidebar.multiselect("Trạng thái đơn hàng:", all_statuses, default=["Completed"])

all_cities = sorted(sales["customer_city"].unique())
cities = st.sidebar.multiselect("Thành phố:", all_cities, default=all_cities)

all_categories = sorted(sales["category_name"].unique())
categories = st.sidebar.multiselect("Danh mục sản phẩm:", all_categories, default=all_categories)

if st.sidebar.button("🔄 Làm mới dữ liệu"):
    st.cache_data.clear()
    st.rerun()

st.title("📊 Phân Tích Doanh Số & Hành Vi Mua Hàng (E-Commerce)")
st.caption(f"{start} → {end} · Trạng thái: {', '.join(statuses) or 'không có'}")

if start > end:
    st.warning("Ngày bắt đầu phải trước hoặc bằng ngày kết thúc!")
    st.stop()

df = sales[
    sales["order_date"].between(pd.Timestamp(start), pd.Timestamp(end))
    & sales["order_status"].isin(statuses)
    & sales["customer_city"].isin(cities)
    & sales["category_name"].isin(categories)
]

if df.empty:
    st.warning("Không tìm thấy dữ liệu phù hợp với bộ lọc!")
    st.stop()

revenue = df["line_revenue"].sum()
orders = df["order_id"].nunique()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Tổng Doanh Thu", f"{revenue:,.0f} USD")
k2.metric("Số Đơn Hàng", f"{orders} đơn")
k3.metric("Giá Trị Trung Bình/Đơn (AOV)", f"{revenue / orders:,.2f} USD")
k4.metric("Tổng Sản Phẩm Bán Ra", f"{int(df['order_quantity'].sum())} sản phẩm")

st.divider()

left, right = st.columns(2)

with left:
    st.subheader("Biến Động Doanh Thu Theo Ngày")
    daily = (df.groupby("order_date")["line_revenue"].sum()
               .reindex(pd.date_range(start, end, name="order_date"), fill_value=0)
               .reset_index())
    fig = px.line(daily, x="order_date", y="line_revenue", markers=True,
                  labels={"order_date": "Ngày", "line_revenue": "Doanh Thu ($)"})
    st.plotly_chart(fig)

with right:
    st.subheader("Top 5 Sản Phẩm Bán Chạy")
    top5 = (df.groupby("product_name", as_index=False)
              .agg(units=("order_quantity", "sum"), revenue=("line_revenue", "sum"))
              .sort_values(["units", "revenue"], ascending=False)
              .head(5))
    fig = px.bar(top5, x="units", y="product_name", orientation="h", text="units",
                 hover_data={"revenue": ":,.0f"},
                 labels={"units": "Số Lượng", "product_name": "Sản Phẩm", "revenue": "Doanh Thu ($)"})
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(fig)

st.divider()

detail = df.assign(order_date=df["order_date"].dt.date).rename(columns=DETAIL_COLUMNS)

st.subheader(f"Bảng Dữ Liệu Chi Tiết ({len(detail)} dòng)")
st.dataframe(detail, hide_index=True)

st.download_button(
    "📥 Tải xuống CSV",
    data=detail.to_csv(index=False).encode("utf-8-sig"),
    file_name=f"chi_tiet_don_hang_{start}_{end}.csv",
    mime="text/csv",
)
