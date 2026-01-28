import streamlit as st
import pandas as pd
import plotly.express as px
import os
import uuid
from datetime import datetime, date, timedelta

# --- CONFIGURATION ---
st.set_page_config(page_title="Blaze Factory Control", layout="wide", page_icon="🏭")

# ⚠️ KEEPING YOUR DATA SAFE
DATA_FILE = "production_data_v29.csv"

# --- CUSTOM FACTORY STAGES ---
STAGES = [
    "1- In Pipeline",
    "2- Sublimation",
    "3- Cutting",
    "4- Print / Emb.",
    "5- Stitching",
    "6- Checking",
    "7- Packing",
    "8- Shipped"
]

# --- FUNCTIONS ---
def load_data():
    if not os.path.exists(DATA_FILE):
        columns = ["Unique ID", "Order ID", "Client", "Due Date", "Priority", "Product Name", "Color", "Article No", "Size Variant", "Total Qty", "Current Stage", "Notes"]
        return pd.DataFrame(columns=columns)
    try:
        df = pd.read_csv(DATA_FILE, dtype=str)
        df = df.fillna("")
        
        # --- ROBUST DATA CLEANING ---
        if 'Order ID' in df.columns:
            df['Order ID'] = df['Order ID'].astype(str).str.replace(r'\.0$', '', regex=True)
        if 'Unique ID' in df.columns:
            df['Unique ID'] = df['Unique ID'].astype(str).str.replace(r'\.0$', '', regex=True)
        if 'Due Date' in df.columns:
            df['Due Date'] = pd.to_datetime(df['Due Date'], errors='coerce')
        if 'Current Stage' in df.columns:
            df['Current Stage'] = df['Current Stage'].replace("1- Material", "1- In Pipeline")
            
        return df
    except Exception as e:
        return pd.DataFrame(columns=["Unique ID", "Order ID", "Client", "Due Date", "Priority", "Product Name", "Color", "Article No", "Size Variant", "Total Qty", "Current Stage", "Notes"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def calculate_status(row):
    if row['Current Stage'] == "8- Shipped": return "Shipped"
    elif row['Current Stage'] == "7- Packing": return "Completed"
    try:
        if pd.isna(row['Due Date']): return "Unknown"
        due = row['Due Date'].date() if isinstance(row['Due Date'], pd.Timestamp) else row['Due Date']
        days_left = (due - date.today()).days
        if days_left < 0: return "OVERDUE"
        elif days_left <= 3: return "CRITICAL"
        else: return "Normal"
    except: return "Unknown"

def get_sorted_active_orders(df_data):
    active_only = df_data[df_data['Current Stage'] != "8- Shipped"]
    if active_only.empty: return []
    order_dates = active_only.groupby('Order ID')['Due Date'].min()
    order_dates_sorted = order_dates.fillna(pd.Timestamp.max).sort_values()
    return order_dates_sorted.index.tolist()

# --- SIDEBAR ---
if 'order_draft' not in st.session_state: st.session_state.order_draft = []

st.sidebar.title("🏭 Archetype")
st.sidebar.markdown("**System V72**")
menu = st.sidebar.radio("NAVIGATE", [
    "Dashboard", 
    "Create Order", 
    "👁️ ORDER DASHBOARD", 
    "🛠️ MANAGE DATA", 
    "Pending Report", 
    "History"
])

df = load_data()

# --- 1. DASHBOARD ---
if menu == "Dashboard":
    st.header("🏭 Archetype Orders Dashboard")
    st.markdown("---")
    
    if df.empty:
        st.info("System is empty. Go to 'Create Order' to add data.")
    else:
        df['Status_Calc'] = df.apply(calculate_status, axis=1)
        df['Total Qty'] = pd.to_numeric(df['Total Qty'], errors='coerce').fillna(0)
        
        active_items = df[~df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
        finished_items = df[df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
        
        critical_items = active_items[active_items['Status_Calc'].isin(["CRITICAL", "OVERDUE"])]
        high_pri_items = active_items[active_items['Priority'].isin(["High", "Urgent"])]
        
        urgent_count_num = len(high_pri_items['Order ID'].unique())
        critical_count_num = len(critical_items['Order ID'].unique())

        active_with_dates = active_items.dropna(subset=['Due Date'])
        if not active_with_dates.empty:
            last_date = active_with_dates['Due Date'].max()
            last_date_str = last_date.strftime('%b %d')
            days_until_last = (last_date.date() - date.today()).days
            last_deadline_msg = f"{last_date_str}"
            if days_until_last >= 0: last_deadline_delta = f"in {days_until_last} Days"
            else: last_deadline_delta = f"{abs(days_until_last)} Days Ago"
        else:
            last_deadline_msg = "No Dates"; last_deadline_delta = "-"

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("📦 Active Orders", len(active_items['Order ID'].unique()))
        k2.metric("👕 Pieces on Floor", f"{int(active_items['Total Qty'].sum()):,}")
        k3.metric("✅ Pieces Finished", f"{int(finished_items['Total Qty'].sum()):,}")
        
        if urgent_count_num > 0: k4.metric("🔥 High Priority", urgent_count_num, delta="See List ⬇️", delta_color="inverse")
        else: k4.metric("🔥 High Priority", 0, delta="All Good")
            
        k5.metric("🏁 Final Deadline", last_deadline_msg, last_deadline_delta)
        
        st.markdown("---")

        if not critical_items.empty or not high_pri_items.empty:
            st.subheader("⚠️ Action Center (Attention Required)")
            c_left, c_right = st.columns(2)
            with c_left:
                if not high_pri_items.empty:
                    st.warning(f"🔥 **{urgent_count_num} High Priority Orders**")
                    pri_summary = high_pri_items.groupby(['Order ID', 'Client', 'Priority'])['Total Qty'].sum().reset_index()
                    st.dataframe(pri_summary, use_container_width=True, hide_index=True)
                else: st.info("ℹ️ No High Priority orders.")

            with c_right:
                if not critical_items.empty:
                    st.error(f"🚨 **{critical_count_num} Orders Due Soon (< 3 Days)**")
                    crit_summary = critical_items.groupby(['Order ID', 'Client', 'Due Date'])['Total Qty'].sum().reset_index()
                    crit_summary['Due Date'] = crit_summary['Due Date'].dt.date
                    
                    today = date.today()
                    def get_sort_key(d): return (d - today).days if isinstance(d, date) else 999
                    def get_status_label(d):
                        days = (d - today).days if isinstance(d, date) else 999
                        if days < 0: return f"⚠️ OVERDUE ({abs(days)} days)"
                        elif days == 0: return "🚨 DUE TODAY"
                        elif days == 1: return "🔥 1 Day Left"
                        else: return f"📅 {days} Days Left"

                    crit_summary['sort_val'] = crit_summary['Due Date'].apply(get_sort_key)
                    crit_summary = crit_summary.sort_values('sort_val', ascending=True)
                    crit_summary['Time Left'] = crit_summary['Due Date'].apply(get_status_label)
                    st.dataframe(crit_summary[['Time Left', 'Order ID', 'Client', 'Total Qty']], use_container_width=True, hide_index=True)
                else: st.success("✅ No critical deadlines.")
            st.markdown("---")

        c1, c2 = st.columns([3, 2])
        with c1:
            st.subheader("📍 Where is the stock stuck?")
            template_stages = pd.DataFrame({"Current Stage": STAGES[:-2]})
            grouped_stage_data = active_items.groupby("Current Stage").agg(Total_Pieces=('Total Qty', 'sum'), Order_Count=('Order ID', 'nunique'), Order_List=('Order ID', lambda x: ', '.join(sorted(x.unique())))).reset_index()
            final_stage_data = pd.merge(template_stages, grouped_stage_data, on="Current Stage", how="left")
            final_stage_data['Total_Pieces'] = final_stage_data['Total_Pieces'].fillna(0)
            final_stage_data['Order_Count'] = final_stage_data['Order_Count'].fillna(0).astype(int)
            final_stage_data['Order_List'] = final_stage_data['Order_List'].fillna("")
            
            fig_flow = px.bar(final_stage_data, x='Current Stage', y='Total_Pieces', text='Total_Pieces', title="Total Pieces Pending by Department", color='Total_Pieces', color_continuous_scale='Reds',
                hover_data={'Current Stage': True, 'Total_Pieces': True, 'Order_Count': True, 'Order_List': True}, labels={'Total_Pieces': 'Pieces', 'Order_Count': 'Orders Involved', 'Order_List': 'IDs'})
            fig_flow.update_traces(textposition='outside')
            st.plotly_chart(fig_flow, use_container_width=True)
            
        with c2:
            st.subheader("👥 Client Workload")
            if not active_items.empty:
                client_agg = active_items.groupby("Client").agg({'Total Qty': 'sum', 'Order ID': lambda x: ', '.join(sorted(x.unique()))}).reset_index().sort_values(by="Total Qty", ascending=False)
                fig_client = px.pie(client_agg, values='Total Qty', names='Client', title="Pending Pieces by Client", hole=0.4, hover_data=['Order ID'])
                st.plotly_chart(fig_client, use_container_width=True)

# --- 2. CREATE ORDER ---
elif menu == "Create Order":
    st.header("📝 Create New Order")
    
    existing_clients = sorted([x for x in df['Client'].unique() if x != ""]) if not df.empty else []
    existing_products = sorted([x for x in df['Product Name'].unique() if x != ""]) if not df.empty else []
    existing_colors = sorted([x for x in df['Color'].unique() if x != ""]) if not df.empty else []
    existing_articles = sorted([x for x in df['Article No'].unique() if x != ""]) if not df.empty else []
    
    with st.container():
        c1, c2 = st.columns(2)
        order_id = c1.text_input("Order ID", placeholder="BFW-001")
        
        client_options = ["➕ Type New..."] + existing_clients
        selected_client = c2.selectbox("Client", client_options, index=1 if existing_clients else 0)
        if selected_client == "➕ Type New...": client = c2.text_input("Enter New Client Name", placeholder="e.g. Nike")
        else: client = selected_client

    is_duplicate = False
    if order_id:
        if order_id in df['Order ID'].values:
            st.error(f"⛔ STOP: The Order ID '{order_id}' already exists!")
            is_duplicate = True
        else:
            st.success("✅ Order ID is available.")

    st.markdown("---")
    st.subheader("Add Product Details")
    
    with st.container():
        c4, c5, c6, c7 = st.columns(4)
        prod_options = ["➕ Type New..."] + existing_products
        selected_prod = c4.selectbox("Product", prod_options, index=1 if existing_products else 0)
        if selected_prod == "➕ Type New...": p_name = c4.text_input("Enter Product Name", placeholder="Hoodie")
        else: p_name = selected_prod
            
        col_options = ["➕ Type New..."] + existing_colors
        selected_col = c5.selectbox("Color", col_options, index=1 if existing_colors else 0)
        if selected_col == "➕ Type New...": p_color = c5.text_input("Enter New Color", placeholder="e.g. Black")
        else: p_color = selected_col

        art_options = ["➕ Type New..."] + existing_articles
        selected_art = c6.selectbox("Article No", art_options, index=1 if existing_articles else 0)
        if selected_art == "➕ Type New...": art_no = c6.text_input("Enter New Article No", placeholder="HD-X")
        else: art_no = selected_art

        p_due_date = c7.date_input("Item Deadline", min_value=date.today(), value=date.today() + timedelta(days=14))
        
        inputs = {}
        st.write("###### Apparel: Youth Sizes")
        y_cols = st.columns(5)
        youth_sizes = ["YXS", "YS", "YM", "YL", "YXL"]
        for i, size in enumerate(youth_sizes): inputs[size] = y_cols[i].number_input(size, min_value=0, key=f"y_{i}")
        st.write("###### Apparel: Adult Sizes")
        a_cols = st.columns(8)
        adult_sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "Other"]
        for i, size in enumerate(adult_sizes): inputs[size] = a_cols[i].number_input(size, min_value=0, key=f"a_{i}")
        st.write("###### 🥊 Boxing / Gear Sizes (oz)")
        g_cols = st.columns(8)
        glove_sizes = ["4oz", "6oz", "8oz", "10oz", "12oz", "14oz", "16oz", "18oz"]
        for i, size in enumerate(glove_sizes): inputs[size] = g_cols[i].number_input(size, min_value=0, key=f"g_{i}")
        
        current_prod_total = sum(inputs.values())
        if current_prod_total > 0: st.info(f"📊 **This Product Total:** {current_prod_total} pcs")
        else: st.caption("Enter sizes to see total.")

        if st.button("Add to List ⬇️", disabled=is_duplicate):
            if is_duplicate: st.error("Cannot add items. Change Order ID first.")
            elif p_name and current_prod_total > 0:
                is_in_list = False
                check_color = p_color if p_color else "Std"
                for item in st.session_state.order_draft:
                    if (item['Product Name'] == p_name and item['Color'] == check_color and item['Article No'] == art_no):
                        is_in_list = True; break
                
                if is_in_list: st.warning("⚠️ This item (Product + Color + Article) is already in your list! (Duplicate Blocked)")
                else:
                    for size, qty in inputs.items():
                        if qty > 0:
                            st.session_state.order_draft.append({
                                "Product Name": p_name, "Color": check_color, "Article No": art_no, 
                                "Size Variant": size, "Total Qty": qty, "Due Date": p_due_date, "Notes": ""
                            })
                    st.success(f"Added {p_name} ({current_prod_total} pcs)")
                    for i in range(5): st.session_state[f"y_{i}"] = 0
                    for i in range(8): st.session_state[f"a_{i}"] = 0
                    for i in range(8): st.session_state[f"g_{i}"] = 0
                    st.rerun()

    if st.session_state.order_draft:
        st.markdown("---")
        grand_total = sum(item['Total Qty'] for item in st.session_state.order_draft)
        st.info(f"🛒 **CURRENT ORDER TOTAL: {grand_total} PCS**")
        st.write("### 🛒 Review & Edit Items Before Saving")
        draft_df = pd.DataFrame(st.session_state.order_draft)
        edited_draft_df = st.data_editor(draft_df, num_rows="dynamic", use_container_width=True, key="draft_editor", column_config={"Due Date": st.column_config.DateColumn("Deadline", format="YYYY-MM-DD")})
        
        if is_duplicate: st.warning("⚠️ You cannot save this order because the Order ID already exists.")
        else:
            if st.button("✅ SAVE FINAL ORDER"):
                if not order_id: st.error("⛔ You must enter an Order ID!")
                elif edited_draft_df.empty: st.error("List is empty!")
                else:
                    new_rows = []
                    for index, row in edited_draft_df.iterrows():
                        if pd.isna(row['Product Name']) or row['Product Name'] == "" or row['Total Qty'] == 0: continue
                        new_rows.append({
                            "Unique ID": str(uuid.uuid4())[:8], "Order ID": order_id, "Client": client, 
                            "Due Date": row['Due Date'], "Priority": "Normal", "Product Name": row['Product Name'], 
                            "Color": row['Color'], "Article No": row['Article No'], "Size Variant": row['Size Variant'], 
                            "Total Qty": row['Total Qty'], "Current Stage": STAGES[0], "Notes": row.get('Notes', "")
                        })
                    if len(new_rows) > 0:
                        df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                        save_data(df); st.session_state.order_draft = []; st.success("Saved!"); st.rerun()

# --- 3. ORDER DASHBOARD ---
elif menu == "👁️ ORDER DASHBOARD":
    st.header("👁️ Single Order Dashboard")
    active_df = df[df['Current Stage'] != "8- Shipped"] 
    if active_df.empty: st.info("No active orders.")
    else:
        # --- ORDER SEARCH / SELECTOR ---
        sorted_orders = get_sorted_active_orders(active_df)
        selected_order = st.selectbox(
            "🔍 Search & Select Order to View Details:", 
            sorted_orders, 
            index=None,  # Default to empty
            placeholder="Click to see list or type Order ID..."
        )
        
        st.markdown("---")

        # --- IF ORDER SELECTED: SHOW DETAILS ---
        if selected_order:
            order_data = df[df['Order ID'] == selected_order]
            if not order_data.empty:
                client_name = order_data.iloc[0]['Client']
                order_data['Total Qty'] = pd.to_numeric(order_data['Total Qty'], errors='coerce').fillna(0)
                total_target = order_data['Total Qty'].sum()
                completed_items = order_data[order_data['Current Stage'].isin(["7- Packing", "8- Shipped"])]
                completed_qty = completed_items['Total Qty'].sum()
                pending_qty = total_target - completed_qty
                if pending_qty < 0: pending_qty = 0
                prog_pct = completed_qty / total_target if total_target > 0 else 0
                
                active_only = order_data[order_data['Current Stage'] != "8- Shipped"]
                if active_only.empty: dates_list = order_data['Due Date'].unique()
                else: dates_list = active_only['Due Date'].unique()

                try:
                    valid_dates = []
                    for d in dates_list:
                        if pd.isna(d): continue
                        if isinstance(d, pd.Timestamp): valid_dates.append(d.date())
                        else: valid_dates.append(d)
                    if valid_dates:
                        next_deadline = min(valid_dates)
                        days_left = (next_deadline - date.today()).days
                        if days_left < 0: time_msg = f"Overdue by {abs(days_left)} Days"; big_text = f"⚠️ {abs(days_left)} Days Overdue"; time_color = "#ff4b4b"
                        elif days_left <= 3: time_msg = f"Urgent: {days_left} Days Left"; big_text = f"🔥 {days_left} Days Left"; time_color = "#ffa421"
                        else: time_msg = f"Due in {days_left} Days"; big_text = f"📅 {days_left} Days Left"; time_color = "#00cc96"
                    else: time_msg = "No Deadline Set"; big_text = "No Date"; time_color = "gray"
                except: time_msg = "Error Calculation"; big_text = "Error"; time_color = "gray"

                st.markdown(f"""<div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left: 8px solid {time_color};"><div style="display:flex; justify-content:space-between; align-items:center;"><div><h2 style="margin:0; color:#31333F;">{client_name} <span style="font-size: 20px; color:gray;">({selected_order})</span></h2><p style="margin:0; color:gray;">Status: <b>{time_msg}</b></p></div><h1 style="margin:0; color:{time_color}; font-size:35px;">{big_text}</h1></div></div>""", unsafe_allow_html=True)
                if len(valid_dates) > 1:
                    with st.expander("📅 View Deadline Breakdown"):
                        timeline_df = active_only.groupby(['Product Name', 'Color', 'Due Date'])['Total Qty'].sum().reset_index().sort_values('Due Date')
                        st.dataframe(timeline_df, use_container_width=True)
                st.markdown("---")
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.write("#### 📊 Progress Metrics")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("🎯 Target", f"{int(total_target)}")
                    m2.metric("✅ Completed", f"{int(completed_qty)}")
                    m3.metric("🚧 Pending", f"{int(pending_qty)}")
                    st.write("")
                    st.progress(prog_pct, text=f"Overall Completion: {int(prog_pct*100)}%")
                with c2:
                    stage_counts = order_data.groupby("Current Stage")['Total Qty'].sum().reset_index()
                    fig = px.pie(stage_counts, values='Total Qty', names='Current Stage', title="Stock Location", hole=0.4)
                    fig.update_layout(margin=dict(t=30, b=0, l=0, r=0), height=250)
                    st.plotly_chart(fig, use_container_width=True)
                st.markdown("---")
                st.subheader("🛠️ Update Production Stage")
                order_data['Display_Name'] = order_data['Product Name'].astype(str) + " (" + order_data['Color'].astype(str) + ")"
                products = order_data['Display_Name'].unique()
                tabs = st.tabs([f"👕 {p}" for p in products])
                for i, p_display in enumerate(products):
                    with tabs[i]:
                        prod_df = order_data[order_data['Display_Name'] == p_display]
                        st.subheader(f"📊 Matrix: {p_display}")
                        matrix_rows = []
                        for _, row in prod_df.iterrows():
                            r = {"Batch ID": row['Unique ID'], "Size": row['Size Variant']}
                            for stage in STAGES:
                                if row['Current Stage'] == stage: r[stage] = f"📍 {row['Total Qty']}"
                                else: r[stage] = ""
                            matrix_rows.append(r)
                        if len(matrix_rows) > 0: st.dataframe(pd.DataFrame(matrix_rows).drop(columns=["Batch ID"]), use_container_width=True)
                        st.markdown("---")
                        st.subheader("🚀 Bulk Action")
                        active_prod_df = prod_df[prod_df['Current Stage'] != "8- Shipped"]
                        if not active_prod_df.empty:
                            c_bulk1, c_bulk2 = st.columns([3, 1])
                            bulk_stage = c_bulk1.selectbox("Move ALL pending items to:", STAGES, key=f"blk_stg_{i}")
                            if c_bulk2.button("Move ALL ⏩", key=f"blk_btn_{i}"):
                                ids_to_move = active_prod_df['Unique ID'].astype(str).tolist()
                                df.loc[df['Unique ID'].isin(ids_to_move), 'Current Stage'] = bulk_stage
                                save_data(df); st.success(f"Moved {len(ids_to_move)} batches!"); st.rerun()
                        else: st.success("All items shipped! ✅")
                        st.markdown("---")
                        st.subheader("🛠️ Individual Actions")
                        show_shipped = st.checkbox("✅ Show Shipped Items", key=f"show_ship_{i}")
                        display_df = prod_df if show_shipped else active_prod_df
                        if display_df.empty: st.info("No items.")
                        else:
                            h1, h2, h3, h4, h5 = st.columns([2, 1, 2, 2, 1])
                            h1.markdown("**Size**"); h2.markdown("**Stage**"); h3.markdown("**Qty**"); h4.markdown("**To**"); h5.markdown("**Action**")
                            for _, row in display_df.iterrows():
                                st.markdown("---")
                                c1, c2, c3, c4, c5 = st.columns([2, 1, 2, 2, 1])
                                c1.markdown(f"**{row['Size Variant']}** ({row['Total Qty']} pcs)")
                                c2.info(f"{row['Current Stage']}")
                                is_shipped = row['Current Stage'] == "8- Shipped"
                                move_qty = c3.number_input("Q", min_value=1, max_value=int(row['Total Qty']), value=int(row['Total Qty']), key=f"q_{row['Unique ID']}", label_visibility="collapsed", disabled=is_shipped)
                                try: curr_idx = STAGES.index(row['Current Stage'])
                                except: curr_idx = 0
                                new_stage = c4.selectbox("S", STAGES, index=curr_idx, key=f"s_{row['Unique ID']}", label_visibility="collapsed", disabled=is_shipped)
                                if not is_shipped:
                                    if c5.button("Move", key=f"b_{row['Unique ID']}"):
                                        if STAGES.index(new_stage) < curr_idx: st.error("🚫 Blocked.")
                                        elif new_stage == row['Current Stage']: st.toast("Change stage.")
                                        else:
                                            if move_qty == row['Total Qty']: df.loc[df['Unique ID'] == row['Unique ID'], 'Current Stage'] = new_stage
                                            else:
                                                df.loc[df['Unique ID'] == row['Unique ID'], 'Total Qty'] = row['Total Qty'] - move_qty
                                                new_row = row.copy(); new_row['Unique ID'] = str(uuid.uuid4())[:8]; new_row['Total Qty'] = move_qty; new_row['Current Stage'] = new_stage
                                                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                                            save_data(df); st.success("Updated!"); st.rerun()
        
        # --- IF NO ORDER SELECTED: SHOW OVERVIEW TABLE ---
        else:
            st.subheader("📋 All Active Orders Overview")
            
            # 1. Group active data to get summaries per order
            overview_data = []
            for oid in sorted_orders:
                o_data = df[df['Order ID'] == oid]
                
                # Basic Stats
                client = o_data.iloc[0]['Client']
                o_data['Total Qty'] = pd.to_numeric(o_data['Total Qty'], errors='coerce').fillna(0)
                total = o_data['Total Qty'].sum()
                
                # Pending Stats
                pending_df = o_data[~o_data['Current Stage'].isin(["7- Packing", "8- Shipped"])]
                pending_qty = pending_df['Total Qty'].sum()
                progress = int(((total - pending_qty) / total * 100) if total > 0 else 0)
                
                # Deadline Logic
                dates = o_data['Due Date'].dropna()
                if not dates.empty:
                    min_date = dates.min()
                    days = (min_date.date() - date.today()).days
                    if days < 0: status = f"⚠️ {abs(days)} Days Overdue"
                    elif days == 0: status = "🚨 Due Today"
                    elif days <= 3: status = f"🔥 {days} Days Left"
                    else: status = f"📅 {days} Days"
                    date_display = min_date.strftime("%Y-%m-%d")
                else:
                    status = "No Date"
                    date_display = "-"

                overview_data.append({
                    "Order ID": oid,
                    "Client": client,
                    "Deadline": date_display,
                    "Status": status,
                    "Total Qty": int(total),
                    "Pending": int(pending_qty),
                    "Progress": f"{progress}%"
                })
            
            if overview_data:
                st.dataframe(pd.DataFrame(overview_data), use_container_width=True, hide_index=True)
            else:
                st.info("No active orders found.")

# --- 4. MANAGE DATA ---
elif menu == "🛠️ MANAGE DATA":
    st.header("🛠️ Data Manager")
    st.info("💡 To DELETE a row: Select it (left click) and press Delete key, or click the Trash icon.")
    search_query = st.text_input("🔍 Search Data (Order ID or Client):", placeholder="Type to filter...")
    if df.empty: st.info("Database is empty.")
    else:
        if search_query:
            search_df = df[df['Order ID'].str.contains(search_query, case=False) | df['Client'].str.contains(search_query, case=False)]
            unique_orders = search_df['Order ID'].dropna().unique()
        else: unique_orders = df['Order ID'].dropna().unique()
        for order_id in unique_orders:
            order_data = df[df['Order ID'] == order_id]
            if not order_data.empty:
                client = order_data.iloc[0]['Client']
                prod_list = ", ".join(order_data['Product Name'].unique())
                with st.expander(f"📝 {order_id} | {client} | {prod_list}"):
                    st.markdown("#### 📅 Update Whole Order Deadline")
                    c_date1, c_date2 = st.columns([2, 1])
                    new_bulk_date = c_date1.date_input("Select new date:", key=f"bd_{order_id}")
                    if c_date2.button("Apply to ALL items", key=f"btn_bd_{order_id}"):
                        df.loc[df['Order ID'] == order_id, 'Due Date'] = pd.to_datetime(new_bulk_date)
                        save_data(df); st.success(f"Updated all items in {order_id} to {new_bulk_date}!"); st.rerun()
                    st.markdown("---")
                    order_data['Due Date'] = pd.to_datetime(order_data['Due Date'], errors='coerce')
                    edited_batch = st.data_editor(order_data, num_rows="dynamic", use_container_width=True, key=f"edit_{order_id}",
                        column_config={"Unique ID": None, "Current Stage": st.column_config.SelectboxColumn("Stage", options=STAGES, required=True), "Priority": st.column_config.SelectboxColumn("Priority", options=["Normal", "High", "Urgent"], required=True), "Due Date": st.column_config.DateColumn("Due Date", format="YYYY-MM-DD"), "Total Qty": st.column_config.NumberColumn("Qty", min_value=0)})
                    if st.button(f"💾 SAVE CHANGES FOR {order_id}", key=f"save_{order_id}"):
                        old_ids = order_data['Unique ID'].tolist()
                        df = df[~df['Unique ID'].isin(old_ids)]
                        final_rows = []
                        for idx, row in edited_batch.iterrows():
                            if pd.isna(row['Unique ID']) or row['Unique ID'] == "": row['Unique ID'] = str(uuid.uuid4())[:8]
                            final_rows.append(row)
                        df = pd.concat([df, pd.DataFrame(final_rows)], ignore_index=True); save_data(df); st.success(f"Updated {order_id}!"); st.rerun()

# --- 5. PENDING REPORT (VISUAL CARDS + SORTING) ---
elif menu == "Pending Report":
    st.header("🚨 Pending Orders Report (By Urgency)")
    search_query = st.text_input("🔍 Search Pending (Order ID or Client):", placeholder="Type to filter...")
    pending_items = df[~df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
    if search_query:
        pending_items = pending_items[pending_items['Order ID'].str.contains(search_query, case=False) | pending_items['Client'].str.contains(search_query, case=False)]
    
    if pending_items.empty: st.success("🎉 No pending orders found!")
    else:
        sorted_pending_orders = get_sorted_active_orders(pending_items)
        st.write(f"Total Pending Orders: **{len(sorted_pending_orders)}**")
        st.markdown("---")
        
        for order_id in sorted_pending_orders:
            full_order_data = df[df['Order ID'] == order_id]
            total_target = pd.to_numeric(full_order_data['Total Qty'], errors='coerce').sum()
            order_pending_data = pending_items[pending_items['Order ID'] == order_id]
            
            if not order_pending_data.empty:
                client = order_pending_data.iloc[0]['Client']
                pending_qty = pd.to_numeric(order_pending_data['Total Qty'], errors='coerce').sum()
                completed_qty = total_target - pending_qty
                if completed_qty < 0: completed_qty = 0
                
                prog_val = completed_qty / total_target if total_target > 0 else 0
                prog_pct_display = int(prog_val * 100)
                
                dates = order_pending_data['Due Date'].dropna().unique()
                try:
                    valid_dates = [d for d in dates if not pd.isna(d)]
                    if valid_dates:
                        clean_dates = []
                        for d in valid_dates:
                            if isinstance(d, pd.Timestamp): clean_dates.append(d.date())
                            else: clean_dates.append(d)
                        earliest_due = sorted(clean_dates)[0]
                        delta = (earliest_due - date.today()).days
                        if delta < 0: date_str = f"⚠️ {earliest_due} ({abs(delta)} days overdue)"; date_color = "red"
                        elif delta <= 3: date_str = f"🔥 {earliest_due} ({delta} days left)"; date_color = "orange"
                        else: date_str = f"📅 {earliest_due}"; date_color = "green"
                    else: date_str = "No Date"; date_color = "gray"
                except: date_str = "Error"; date_color = "gray"

                with st.container():
                    c_info, c_metrics = st.columns([2, 2])
                    with c_info:
                        st.subheader(f"{client} ({order_id})")
                        st.caption(f"Due: {date_str}")
                    with c_metrics:
                        m1, m2, m3 = st.columns(3)
                        m1.metric("Target", f"{int(total_target)}")
                        m2.metric("Pending", f"{int(pending_qty)}")
                        m3.metric("Done", f"{prog_pct_display}%")
                    st.progress(prog_val)
                    with st.expander("See Details"):
                        st.dataframe(order_pending_data[["Product Name", "Color", "Size Variant", "Current Stage", "Total Qty"]], use_container_width=True)
                    st.markdown("---")

# --- 6. HISTORY ---
elif menu == "History":
    st.header("📂 Order History")
    search_query = st.text_input("🔍 Search History (Order ID or Client):", placeholder="Type to filter...")
    if df.empty: st.info("No history.")
    else:
        unique_orders = df['Order ID'].dropna().unique()
        history_list = []
        for order_id in unique_orders:
            order_data = df[df['Order ID'] == order_id]
            if order_data.empty: continue
            client = order_data.iloc[0]['Client']
            if search_query:
                if (search_query.lower() not in order_id.lower()) and (search_query.lower() not in client.lower()): continue
            
            total_items = len(order_data)
            shipped = len(order_data[order_data['Current Stage'] == "8- Shipped"])
            packed = len(order_data[order_data['Current Stage'] == "7- Packing"])
            if shipped == total_items: rank = 3; status_label = "🚢 SHIPPED"; status_color = "blue"
            elif (shipped + packed) == total_items: rank = 1; status_label = "✅ COMPLETED"; status_color = "green"
            else: rank = 2; status_label = "⏳ IN PROGRESS"; status_color = "orange"
            history_list.append({"rank": rank, "id": order_id, "client": client, "label": status_label, "color": status_color, "data": order_data})
        
        if not history_list: st.warning("No orders match your search.")
        else:
            history_list.sort(key=lambda x: x["rank"])
            for item in history_list:
                with st.expander(f"**{item['id']}** | {item['client']} | :{item['color']}[{item['label']}]"):
                    st.dataframe(item['data'], use_container_width=True)
