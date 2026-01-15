import streamlit as st
import pandas as pd
import plotly.express as px
import os
import uuid
from datetime import datetime, date

# --- CONFIGURATION ---
st.set_page_config(page_title="Blaze Factory Control", layout="wide", page_icon="🏭")

# ⚠️ KEEPS YOUR EXISTING DATA SAFE
DATA_FILE = "production_data_v29.csv"

# --- CUSTOM FACTORY STAGES ---
STAGES = [
    "1- Material",
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
        df = pd.read_csv(DATA_FILE)
        if 'Due Date' in df.columns:
            df['Due Date'] = pd.to_datetime(df['Due Date'], errors='coerce').dt.date
        df = df.fillna("")
        return df
    except Exception as e:
        return pd.DataFrame(columns=["Unique ID", "Order ID", "Client", "Due Date", "Priority", "Product Name", "Color", "Article No", "Size Variant", "Total Qty", "Current Stage", "Notes"])

def save_data(df):
    df.to_csv(DATA_FILE, index=False)

def calculate_status(row):
    if row['Current Stage'] == "8- Shipped": return "Shipped"
    elif row['Current Stage'] == "7- Packing": return "Completed"
    try:
        if pd.isna(row['Due Date']) or row['Due Date'] == "": return "Unknown"
        due = row['Due Date'] if not isinstance(row['Due Date'], str) else datetime.strptime(row['Due Date'], "%Y-%m-%d").date()
        days_left = (due - date.today()).days
        if days_left < 0: return "OVERDUE"
        elif days_left <= 3: return "CRITICAL"
        else: return "Normal"
    except: return "Unknown"

# --- SIDEBAR ---
if 'order_draft' not in st.session_state: st.session_state.order_draft = []

st.sidebar.title("🏭 Blaze Factory")
st.sidebar.markdown("**System V30 (Pro Dashboard)**")
menu = st.sidebar.radio("NAVIGATE", ["Dashboard", "Create Order", "👁️ MONITOR & UPDATE", "🛠️ MANAGE DATA", "Pending Report", "History"])

df = load_data()

# --- 1. DASHBOARD (MAJOR UPGRADE) ---
if menu == "Dashboard":
    st.header("🏭 Executive Command Center")
    st.markdown("---")
    
    if df.empty:
        st.info("System is empty. Go to 'Create Order' to add data.")
    else:
        # Pre-calculations
        df['Status_Calc'] = df.apply(calculate_status, axis=1)
        # Convert Qty to numbers to be safe
        df['Total Qty'] = pd.to_numeric(df['Total Qty'], errors='coerce').fillna(0)
        
        # Filter: Active Items (Not in Packing or Shipped)
        active_items = df[~df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
        # Filter: Finished Items
        finished_items = df[df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
        
        # --- TOP KPI CARDS ---
        k1, k2, k3, k4 = st.columns(4)
        
        k1.metric("📦 Active Orders", len(active_items['Order ID'].unique()))
        
        total_pending_pcs = active_items['Total Qty'].sum()
        k2.metric("👕 Pieces on Floor", f"{int(total_pending_pcs):,}")
        
        total_shipped_pcs = finished_items['Total Qty'].sum()
        k3.metric("✅ Pieces Finished", f"{int(total_shipped_pcs):,}")
        
        urgent_count = len(active_items[active_items['Priority'].isin(["High", "Urgent"])])
        k4.metric("🔥 High Priority Batches", urgent_count, delta="Act Now", delta_color="inverse")
        
        st.markdown("---")
        
        # --- CHARTS SECTION ---
        c1, c2 = st.columns([3, 2])
        
        with c1:
            st.subheader("📍 Where is the stock stuck?")
            # Group by Stage and Sum Quantity
            stage_data = active_items.groupby("Current Stage")['Total Qty'].sum().reindex(STAGES[:-2], fill_value=0).reset_index()
            
            fig_flow = px.bar(
                stage_data, 
                x='Current Stage', 
                y='Total Qty', 
                text='Total Qty',
                title="Total Pieces Pending by Department",
                color='Total Qty',
                color_continuous_scale='Reds'
            )
            fig_flow.update_traces(textposition='outside')
            st.plotly_chart(fig_flow, use_container_width=True)
            
        with c2:
            st.subheader("👥 Client Workload")
            if not active_items.empty:
                client_data = active_items.groupby("Client")['Total Qty'].sum().reset_index().sort_values(by="Total Qty", ascending=False)
                fig_client = px.pie(
                    client_data, 
                    values='Total Qty', 
                    names='Client', 
                    title="Pending Pieces by Client",
                    hole=0.4
                )
                st.plotly_chart(fig_client, use_container_width=True)
            else:
                st.success("No active clients.")

        # --- URGENT ALERTS SECTION ---
        st.markdown("---")
        st.subheader("🚨 Priority Watchlist (High & Urgent)")
        
        # Filter for High/Urgent AND Not Completed
        watchlist = df[
            (df['Priority'].isin(["High", "Urgent"])) & 
            (~df['Current Stage'].isin(["7- Packing", "8- Shipped"]))
        ].copy()
        
        if watchlist.empty:
            st.success("Relax! No urgent items pending.")
        else:
            # Sort by Due Date (Oldest first)
            watchlist = watchlist.sort_values(by="Due Date")
            
            # Show a clean table
            st.dataframe(
                watchlist[[
                    "Due Date", "Client", "Order ID", "Product Name", 
                    "Color", "Size Variant", "Total Qty", "Current Stage", "Priority"
                ]],
                use_container_width=True,
                hide_index=True
            )

# --- 2. CREATE ORDER (Unchanged) ---
elif menu == "Create Order":
    st.header("📝 Create New Order")
    with st.container():
        c1, c2, c3 = st.columns(3)
        order_id = c1.text_input("Order ID", placeholder="BFW-001")
        client = c2.text_input("Client")
        due_date = c3.date_input("Due Date", min_value=date.today())
    st.markdown("---")
    st.subheader("Add Product Details")
    with st.container():
        c4, c5, c6 = st.columns(3)
        p_name = c4.text_input("Product", placeholder="Hoodie")
        p_color = c5.text_input("Color", placeholder="e.g. Black")
        art_no = c6.text_input("Article No", placeholder="HD-X")
        inputs = {}
        st.write("###### Youth Sizes")
        y_cols = st.columns(5)
        youth_sizes = ["YXS", "YS", "YM", "YL", "YXL"]
        for i, size in enumerate(youth_sizes): inputs[size] = y_cols[i].number_input(size, min_value=0, key=f"y_{i}")
        st.write("###### Adult Sizes")
        a_cols = st.columns(8)
        adult_sizes = ["XS", "S", "M", "L", "XL", "2XL", "3XL", "Other"]
        for i, size in enumerate(adult_sizes): inputs[size] = a_cols[i].number_input(size, min_value=0, key=f"a_{i}")
        if st.button("Add to List ⬇️"):
            if p_name and sum(inputs.values()) > 0:
                for size, qty in inputs.items():
                    if qty > 0:
                        st.session_state.order_draft.append({
                            "Product Name": p_name, "Color": p_color if p_color else "Std",
                            "Article No": art_no, "Size Variant": size, "Total Qty": qty, "Notes": ""
                        })
                st.success(f"Added {p_name}")
    if st.session_state.order_draft:
        st.markdown("---")
        st.write("### 🛒 Review & Edit Items Before Saving")
        draft_df = pd.DataFrame(st.session_state.order_draft)
        edited_draft_df = st.data_editor(draft_df, num_rows="dynamic", use_container_width=True, key="draft_editor")
        if st.button("✅ SAVE FINAL ORDER"):
            if edited_draft_df.empty: st.error("List is empty!")
            else:
                new_rows = []
                for index, row in edited_draft_df.iterrows():
                    if pd.isna(row['Product Name']) or row['Product Name'] == "" or row['Total Qty'] == 0: continue
                    new_rows.append({
                        "Unique ID": str(uuid.uuid4())[:8], "Order ID": order_id, "Client": client, "Due Date": due_date, "Priority": "Normal",
                        "Product Name": row['Product Name'], "Color": row['Color'], "Article No": row['Article No'],
                        "Size Variant": row['Size Variant'], "Total Qty": row['Total Qty'], "Current Stage": STAGES[0], "Notes": row.get('Notes', "")
                    })
                if len(new_rows) > 0:
                    df = pd.concat([df, pd.DataFrame(new_rows)], ignore_index=True)
                    save_data(df); st.session_state.order_draft = []; st.success("Saved!"); st.rerun()

# --- 3. MONITOR & UPDATE (Unchanged) ---
elif menu == "👁️ MONITOR & UPDATE":
    st.header("👁️ Production Control Room")
    active_df = df[df['Current Stage'] != "8- Shipped"] 
    if active_df.empty: st.info("No active orders.")
    else:
        valid_orders = active_df['Order ID'].dropna().unique()
        selected_order = st.selectbox("Select Active Order", valid_orders)
        if selected_order:
            order_data = df[df['Order ID'] == selected_order]
            if not order_data.empty:
                client_name = order_data.iloc[0]['Client']
                order_data['Total Qty'] = pd.to_numeric(order_data['Total Qty'], errors='coerce').fillna(0)
                total_target = order_data['Total Qty'].sum()
                completed_qty = order_data[order_data['Current Stage'].isin(["7- Packing", "8- Shipped"])]['Total Qty'].sum()
                pending_qty = total_target - completed_qty
                if pending_qty < 0: pending_qty = 0
                prog_pct = completed_qty / total_target if total_target > 0 else 0
                st.markdown(f"""
                <div style="background-color:#f0f2f6; padding:20px; border-radius:10px; border-left: 6px solid #ff4b4b; margin-bottom: 20px;">
                    <h2 style="margin:0; color:#31333F;">{client_name} <span style="font-size: 20px; color:gray;">({selected_order})</span></h2>
                    <div style="display: flex; gap: 40px; margin-top: 15px;">
                        <div><p style="margin:0; font-size:14px; color:gray;">TOTAL TARGET</p><h3 style="margin:0; font-size:24px;">{int(total_target)} pcs</h3></div>
                        <div><p style="margin:0; font-size:14px; color:gray;">PENDING</p><h3 style="margin:0; font-size:24px; color:#ff4b4b;">{int(pending_qty)} pcs</h3></div>
                        <div><p style="margin:0; font-size:14px; color:gray;">COMPLETED</p><h3 style="margin:0; font-size:24px; color:#00cc96;">{int(completed_qty)} pcs</h3></div>
                    </div>
                </div>""", unsafe_allow_html=True)
                st.progress(prog_pct, text=f"Completion: {int(prog_pct*100)}%")
                order_data['Display_Name'] = order_data['Product Name'] + " (" + order_data['Color'] + ")"
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
                        st.subheader("🛠️ Action Center")
                        active_prod_df = prod_df[prod_df['Current Stage'] != "8- Shipped"]
                        if active_prod_df.empty: st.success("All Shipped! ✅")
                        else:
                            h1, h2, h3, h4, h5 = st.columns([2, 1, 2, 2, 1])
                            h1.markdown("**Size**"); h2.markdown("**Stage**"); h3.markdown("**Qty**"); h4.markdown("**To**"); h5.markdown("**Action**")
                            for _, row in active_prod_df.iterrows():
                                st.markdown("---")
                                c1, c2, c3, c4, c5 = st.columns([2, 1, 2, 2, 1])
                                c1.markdown(f"**{row['Size Variant']}** ({row['Total Qty']} pcs)"); c2.info(f"{row['Current Stage']}")
                                move_qty = c3.number_input("Q", min_value=1, max_value=int(row['Total Qty']), value=int(row['Total Qty']), key=f"q_{row['Unique ID']}", label_visibility="collapsed")
                                curr_idx = STAGES.index(row['Current Stage'])
                                new_stage = c4.selectbox("S", STAGES, index=curr_idx, key=f"s_{row['Unique ID']}", label_visibility="collapsed")
                                if c5.button("Move", key=f"b_{row['Unique ID']}"):
                                    if STAGES.index(new_stage) < curr_idx: st.error("🚫 Blocked: Backward move.")
                                    elif new_stage == row['Current Stage']: st.toast("Change stage.")
                                    else:
                                        if move_qty == row['Total Qty']: df.loc[df['Unique ID'] == row['Unique ID'], 'Current Stage'] = new_stage
                                        else:
                                            df.loc[df['Unique ID'] == row['Unique ID'], 'Total Qty'] = row['Total Qty'] - move_qty
                                            new_row = row.copy(); new_row['Unique ID'] = str(uuid.uuid4())[:8]; new_row['Total Qty'] = move_qty; new_row['Current Stage'] = new_stage
                                            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                                        save_data(df); st.success("Updated!"); st.rerun()

# --- 4. MANAGE DATA (Unchanged) ---
elif menu == "🛠️ MANAGE DATA":
    st.header("🛠️ Data Manager")
    tab1, tab2 = st.tabs(["📝 Edit Data", "🗑️ Delete"])
    with tab1:
        st.caption("Click on an order to edit.")
        if df.empty: st.info("Database is empty.")
        else:
            unique_orders = df['Order ID'].dropna().unique()
            for order_id in unique_orders:
                order_data = df[df['Order ID'] == order_id]
                if not order_data.empty:
                    client = order_data.iloc[0]['Client']
                    prod_list = ", ".join(order_data['Product Name'].unique())
                    with st.expander(f"📝 {order_id} | {client} | {prod_list}"):
                        edited_batch = st.data_editor(order_data, num_rows="dynamic", use_container_width=True, key=f"edit_{order_id}",
                            column_config={"Unique ID": None, "Current Stage": st.column_config.SelectboxColumn("Stage", options=STAGES, required=True), "Priority": st.column_config.SelectboxColumn("Priority", options=["Normal", "High", "Urgent"], required=True), "Due Date": st.column_config.DateColumn("Due Date"), "Total Qty": st.column_config.NumberColumn("Qty", min_value=1)},
                            disabled=["Order ID", "Client", "Product Name", "Color", "Article No", "Notes"])
                        if st.button(f"💾 SAVE CHANGES FOR {order_id}", key=f"save_{order_id}"):
                            df = df[~df['Unique ID'].isin(order_data['Unique ID'].tolist())]
                            df = pd.concat([df, edited_batch], ignore_index=True); save_data(df); st.success(f"Updated {order_id}!"); st.rerun()
    with tab2:
        if not df.empty:
            del_mode = st.radio("Mode", ["Delete Order", "Delete Batch"])
            if del_mode == "Delete Order":
                order_to_del = st.selectbox("Select Order", df['Order ID'].unique())
                if st.button("DELETE ORDER"): df = df[df['Order ID'] != order_to_del]; save_data(df); st.success("Deleted."); st.rerun()
            else:
                df['Label'] = df['Order ID'] + " | " + df['Product Name'] + " | " + df['Size Variant']
                batch_to_del = st.selectbox("Select Batch", df['Label'].unique())
                if st.button("DELETE BATCH"): id_to_del = df[df['Label'] == batch_to_del].iloc[0]['Unique ID']; df = df[df['Unique ID'] != id_to_del].drop(columns=['Label']); save_data(df); st.success("Deleted."); st.rerun()

# --- 5. PENDING REPORT (Unchanged) ---
elif menu == "Pending Report":
    st.header("🚨 Pending Orders Report")
    pending_items = df[~df['Current Stage'].isin(["7- Packing", "8- Shipped"])]
    if pending_items.empty: st.success("🎉 No pending orders!")
    else:
        pending_orders = pending_items['Order ID'].dropna().unique()
        st.write(f"Total Pending Orders: **{len(pending_orders)}**")
        st.markdown("---")
        for order_id in pending_orders:
            order_pending_data = pending_items[pending_items['Order ID'] == order_id]
            if not order_pending_data.empty:
                client = order_pending_data.iloc[0]['Client']; due_date = order_pending_data.iloc[0]['Due Date']
                pending_qty = pd.to_numeric(order_pending_data['Total Qty'], errors='coerce').sum()
                with st.expander(f"🔴 {order_id} | {client} | Pending: {int(pending_qty)} pcs | Due: {due_date}"):
                    st.dataframe(order_pending_data[["Product Name", "Color", "Size Variant", "Current Stage", "Total Qty", "Notes"]], use_container_width=True)

# --- 6. HISTORY (Unchanged) ---
elif menu == "History":
    st.header("📂 Order History")
    if df.empty: st.info("No history.")
    else:
        unique_orders = df['Order ID'].dropna().unique()
        for order_id in unique_orders:
            order_data = df[df['Order ID'] == order_id]
            if not order_data.empty:
                client = order_data.iloc[0]['Client']; total_items = len(order_data)
                shipped = len(order_data[order_data['Current Stage'] == "8- Shipped"])
                packed = len(order_data[order_data['Current Stage'] == "7- Packing"])
                if shipped == total_items: status_label = "🚢 SHIPPED"; status_color = "blue"
                elif (shipped + packed) == total_items: status_label = "✅ COMPLETED"; status_color = "green"
                else: status_label = "⏳ IN PROGRESS"; status_color = "orange"
                with st.expander(f"**{order_id}** | {client} | :{status_color}[{status_label}]"): st.dataframe(order_data, use_container_width=True)
