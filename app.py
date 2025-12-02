# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ 1. DATA LOADING & PREPROCESSING: 支持真实数据 + 模拟数据兜底                  │
# │ ---------------------------------------------------------------------------- │
# │ ★ 核心逻辑：                                                                 │
# │   - 读取 Details.csv 和 Orders.csv 并执行 Inner Join (Order ID)              │
# │   - 若文件缺失，生成与你提供的表结构完全一致的模拟数据                           │
# └──────────────────────────────────────────────────────────────────────────────┘

import dash
from dash import dcc, html, Input, Output, State, callback_context
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ 1. 数据加载                                                                   │
# └──────────────────────────────────────────────────────────────────────────────┘
df_details = pd.read_csv("Details.csv")
df_orders = pd.read_csv("Orders.csv")
# 内连接合并（确保只保留双方都有的 Order ID）
df = pd.merge(df_details, df_orders, on="Order ID", how="inner")
# 标准化 Sub-Categor 数据 
# 这能避免 "Chairs " vs "Chairs" 的问题 
df["Sub-Category"] = df["Sub-Category"].astype(str).str.strip()

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ 2. DASH APP SETUP: UI 布局                                                   │
# └──────────────────────────────────────────────────────────────────────────────┘
# Dash App 初始化 
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# 样式定义
card_style_kpi = {
    "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", # 紫色渐变
    "color": "white",
    "box-shadow": "0 4px 6px rgba(0,0,0,0.1)",
    "border": "none",
    "border-radius": "10px"
}

# # 样式定义 
# card_style_kpi = {
#     "background": "linear-gradient(45deg, #4b6cb7 0%, #182848 100%)", # 蓝色渐变
#     "color": "white",
#     "textAlign": "center"
# } 

app.layout = dbc.Container([
    # ── State Management (存储筛选状态) ──
    # store-subcat: 存储 Sub-Category 的筛选值 (默认 'All')
    dcc.Store(id='store-subcat', data='All'),
    # store-state: 存储 State 的筛选值 (默认 'All')
    dcc.Store(id='store-state', data='All'),
    # store-state: 存储 Customer 的筛选值 (默认 'All')
    dcc.Store(id='store-customer', data='All'),  

    # ── Header & Reset Button ──
    dbc.Row([
        dbc.Col(html.H2("Product Sales Report", className="fw-bold my-3"), width=9),
        dbc.Col(
            dbc.Button("Clear All Filters", id="clear-btn", color="danger", outline=True, size="sm", className="mt-4 w-100"),
            width=3
        )
    ], className="mb-3 border-bottom pb-2"),

    # ── Row 1: 4 KPI Cards ── 
    # 指标：Amount, Profit, Quantity, Order Count 
    dbc.Row([
        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Total Amount", className="opacity-75"),
            html.H3(id="kpi-amount", className="fw-bold")
        ]), style=card_style_kpi), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Total Profit", className="opacity-75"),
            html.H3(id="kpi-profit", className="fw-bold")
        ]), style=card_style_kpi), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Total Quantity", className="opacity-75"),
            html.H3(id="kpi-quantity", className="fw-bold")
        ]), style=card_style_kpi), width=3),

        dbc.Col(dbc.Card(dbc.CardBody([
            html.H6("Total Orders", className="opacity-75"),
            html.H3(id="kpi-orders", className="fw-bold")
        ]), style=card_style_kpi), width=3),
    ], className="mb-4"),

    # ── Row 2: 2 Bar Charts ──
    dbc.Row([
        # Chart 1: Profit by Sub-Category
        dbc.Col(dbc.Card([
            dbc.CardHeader("Total Profit by Sub-Category", className="fw-bold bg-light"),
            dbc.CardBody(dcc.Graph(id="chart-subcat", config={'displayModeBar': False}, style={'height': '350px'}))
        ], className="shadow-sm border-0"), width=4),

        # Chart 2: Sales by State
        dbc.Col(dbc.Card([
            dbc.CardHeader("Total Sales by State", className="fw-bold bg-light"),
            dbc.CardBody(dcc.Graph(id="chart-state", config={'displayModeBar': False}, style={'height': '350px'}))
        ], className="shadow-sm border-0"), width=4),

        # Chart 3: Sales by State
        dbc.Col(dbc.Card([
            dbc.CardHeader("Top 6 Customers by Sales", className="fw-bold bg-light"),
            dbc.CardBody(dcc.Graph(id="chart-customer", config={'displayModeBar': False}, style={'height': '350px'}))
        ], className="shadow-sm border-0 mb-4"), width=4)
    ]),
    
    # 底部状态栏
    dbc.Row(dbc.Col(html.Div(id="filter-status", className="text-muted small mt-3 text-end")))

], fluid=True, className="bg-light vh-100 p-4")

# ┌──────────────────────────────────────────────────────────────────────────────┐
# │ 3. CALLBACKS: 交互逻辑核心 (Cross-filtering)                                  │
# └──────────────────────────────────────────────────────────────────────────────┘

# ── Dash 交互问题的核心修复：添加 chart-subcat.clickData 和 chart-state.clickData 到 Output ──
# 这样我们可以在回调结束时将它们重置为 None
# 在 Dash 中, dcc.Graph 的 clickData 属性只有在数据发生变化时才会触发回调。
# 当你点击 "Chairs" 时, clickData 变成了 {'points': [{'y': 'Chairs', ...}]}，回调触发，筛选生效。
# 当你再次点击 "Chairs" 时, clickData 的值仍然是 {'points': [{'y': 'Chairs', ...}]}。因为值没有变化, Dash 不会再次触发回调。
# 解决方案： 我们需要在回调结束时，手动将图表的 clickData 重置为 None。这样下次点击同一个条形时, clickData 就会从 None 变为 "Chairs"，从而被 Dash 判定为“变化”，再次触发回调
@app.callback(
    # 当前用户选中的【子类别】列表 
    [Output('store-subcat', 'data'), 
    # 当前用户选中的【州】列表
     Output('store-state', 'data'),
     # 当前用户选中的【客户】列表 
     Output('store-customer', 'data'),
     # 用来保存当前选项，供所有下游图表读取并过滤数据, 重置子类别图的点击高亮选中状态 (视觉效果) 
     Output('chart-subcat', 'clickData'),
     # 用来保存当前选项，供所有下游图表读取并过滤数据, 重置州图的点击高亮选中状态 (视觉效果)  
     Output('chart-state', 'clickData'),
     # 用来保存当前选项，供所有下游图表读取并过滤数据, 重置客户图的点击高亮选中状态 (视觉效果)  
     Output('chart-customer', 'clickData')], 
     # 点“清除”按钮   
    [Input('clear-btn', 'n_clicks'),
    # 点击子类别柱状图 
     Input('chart-subcat', 'clickData'),
     # 点击州图
     Input('chart-state', 'clickData'),
     # 点击客户图
     Input('chart-customer', 'clickData')],
     # 状态 
    [State('store-subcat', 'data'), 
    State('store-state', 'data'),
    State('store-customer', 'data')]
)
def update_filters(n_clicks, click_sub, click_state, click_cust, curr_sub, curr_state, curr_cust):
    ctx = callback_context
    if not ctx.triggered:
        return "All", "All", "All", None, None, None
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    # 1. 如果是因为 clickData 被重置为 None 而触发的回调，直接忽略，不更新状态
    # (这是为了防止重置操作导致状态丢失或死循环)
    # (prevent infinite loops) 
        # 正确的防重置触发逻辑
    if (trigger_id == 'chart-subcat' and click_sub is None) or \
       (trigger_id == 'chart-state' and click_state is None) or \
       (trigger_id == 'chart-customer' and click_cust is None):
        raise PreventUpdate

    # 2. Clear all
    if trigger_id == 'clear-btn':
        # 对应回调函数中定义的 6 个 Output 
        return "All", "All", "All", None, None, None  

    # 3. 处理点击逻辑
    # 重点：每次返回时，最后两个参数传 None，这样图表的 clickData 就会被清空
    # 下次再点同一个位置时，clickData 就会从 None 变为 "Value"，从而触发回调

    # Helper for Toggle Logic  
    def toggle_filter(click_data, current_val, key='x'):
        try:
            clicked_val = str(click_data['points'][0][key]).strip()
            # If clicking the already selected item, reset to All (Toggle off) 
            # Toggle 逻辑：如果点的和当前一样，则取消筛选(All) 
            if str(current_val) != "All" and clicked_val == str(current_val):
                return "All"
            return clicked_val
        except:
            return current_val

    # Sub-Category 图（水平 → 用 'y'）
    if trigger_id == 'chart-subcat' and click_sub:
        new_sub = toggle_filter(click_sub, curr_sub, key='y')
        return new_sub, curr_state, curr_cust, None, None, None 

    # State 图（垂直 → 用 'x'）
    if trigger_id == 'chart-state' and click_state:
        new_state = toggle_filter(click_state, curr_state, key='x')
        return curr_sub, new_state, curr_cust, None, None, None 

    # 3. Customer 图（垂直 → 用 'x'） 
    if trigger_id == 'chart-customer' and click_cust:
        new_cust = toggle_filter(click_cust, curr_cust, key='x')
        return curr_sub, curr_state, new_cust, None, None, None

    return curr_sub, curr_state, curr_cust, None, None, None 


@app.callback(
    # ==================== 输出部分（共 8 个）====================
    # 这些是回调函数需要更新/返回新值的组件和属性
    [Output('kpi-amount', 'children'),      # 总销售额 KPI 卡片显示的数字/文字
     Output('kpi-profit', 'children'),      # 总利润 KPI 卡片显示的内容
     Output('kpi-quantity', 'children'),    # 销售数量 KPI
     Output('kpi-orders', 'children'),      # 订单数量 KPI
     Output('chart-subcat', 'figure'),      # 子类别销量图（柱状图/饼图等），完整更新 figure 对象
     Output('chart-state', 'figure'),       # 地区（州/省）销量分布图，完整更新 figure
     Output('chart-customer', 'figure'),    # 客户分析图，完整更新 figure
     Output('filter-status', 'children'),],  # 显示当前过滤条件的文字提示 

    # ==================== 输入部分（共 3 个）====================
    # 只要以下任一组件的属性发生变化，就会触发回调函数执行
    [Input('store-subcat', 'data'),         # dcc.Store 存储的用户选择的【子类别】列表）
     Input('store-state', 'data'),          # dcc.Store 存储的用户选择的【地区/州】列表
     Input('store-customer', 'data')]       # dcc.Store 存储的用户选择的【客户】列表 
)
def update_ui(sel_sub, sel_state, sel_cust):
    # ── 辅助函数：获取筛选后的数据 ────────────────
    # Helper to filter data based on stores
    # "ignore_X=True" allows that specific chart to show all bars (context) while highlighting selection
    def get_filtered_df(ignore_sub=False, ignore_state=False, ignore_cust=False):
        d = df.copy()
        if not ignore_sub and sel_sub != "All":
            d = d[d["Sub-Category"] == sel_sub]
        if not ignore_state and sel_state != "All":
            d = d[d["State"] == sel_state]
        if not ignore_cust and sel_cust != "All":
            d = d[d["CustomerName"] == sel_cust]
        return d

    # ── 辅助函数：统一“No Data”样式 ────────────────
    def create_no_data_figure():
        fig = go.Figure()
        fig.add_annotation(
            text="No Data",
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=20, color="gray"),
            opacity=0.6
        )
        fig.update_layout(
            xaxis_visible=False,
            yaxis_visible=False,
            margin=dict(t=10, l=10, r=10, b=10)
        )
        return fig
    
    # ── 1. KPI 计算 ──────────────
    df_kpi = get_filtered_df()
    
    if df_kpi.empty:
        k_amt, k_prof, k_qty, k_ords = "$0", "$0", "0", "0"
    else:
        k_amt = f"${df_kpi['Amount'].sum():,.0f}"
        k_prof = f"${df_kpi['Profit'].sum():,.0f}"
        k_qty = f"{df_kpi['Quantity'].sum():,}"
        k_ords = f"{df_kpi['Order ID'].nunique():,}"

    # ── 2. Sub-Category 图表 ──
    df_sub_ctx = get_filtered_df(ignore_sub=True)
    if df_sub_ctx.empty:
        fig_sub = create_no_data_figure()
    else:
        sub_group = df_sub_ctx.groupby("Sub-Category")["Profit"].sum().reset_index().sort_values("Profit", ascending=False).head(6)
        fig_sub = px.bar(sub_group, x="Profit", y="Sub-Category", text_auto='.2s', orientation='h')
        colors = ['#764ba2' if (sel_sub == "All" or x == sel_sub) else '#e0e0e0' for x in sub_group["Sub-Category"]]
        fig_sub.update_traces(marker_color=colors)
        fig_sub.update_layout(margin=dict(t=10, l=80, r=20, b=10), xaxis_title="Profit", yaxis_title=None, yaxis={'autorange': 'reversed'})

    # ── 3. State 图表 ──
    df_state_ctx = get_filtered_df(ignore_state=True)
    if df_state_ctx.empty:
        fig_sub = create_no_data_figure()
    else:
        state_group = df_state_ctx.groupby("State")["Amount"].sum().reset_index().sort_values("Amount", ascending=False).head(6)
        fig_state = px.bar(state_group, x="State", y="Amount", text_auto='.2s')
        colors = ['#667eea' if (sel_state == "All" or x == sel_state) else '#e0e0e0' for x in state_group["State"]]
        fig_state.update_traces(marker_color=colors)
        fig_state.update_layout(margin=dict(t=10, l=10, r=10, b=10), yaxis_title="Amount", xaxis_title=None)

    # ── 4. Customer 图表 ──
    df_cust_ctx = get_filtered_df(ignore_cust=True)
    if df_cust_ctx.empty:
        fig_sub = create_no_data_figure()
    else:
        cust_group = df_cust_ctx.groupby("CustomerName")["Amount"].sum().reset_index().sort_values("Amount", ascending=False).head(6)
        fig_cust = px.bar(cust_group, x="CustomerName", y="Amount", text_auto='.2s')
        colors_c = ['#182848' if (sel_cust == "All" or x == sel_cust) else '#e0e0e0' for x in cust_group["CustomerName"]]
        fig_cust.update_traces(marker_color=colors_c)
        fig_cust.update_layout(margin=dict(t=10, l=10, r=10, b=10), yaxis_title="Amount", xaxis_title=None)

    status = f"Filters | Sub-Cat: {sel_sub} | State: {sel_state} | Customer: {sel_cust}"

    return k_amt, k_prof, k_qty, k_ords, fig_sub, fig_state, fig_cust, status  

if __name__ == "__main__":
    app.run_server(debug=True)