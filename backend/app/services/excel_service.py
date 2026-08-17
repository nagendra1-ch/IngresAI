import io
import pandas as pd
from typing import List
from app.models import User, QueryHistory

class ExcelService:
    @staticmethod
    def generate_admin_report(users: List[User], queries: List[QueryHistory], accesses: List[dict], summary_stats: dict) -> io.BytesIO:
        """
        Generates a multi-sheet Excel report for administrators containing user tables,
        queries, district access counters, and high level summaries.
        """
        buffer = io.BytesIO()
        
        # We use pd.ExcelWriter with openpyxl engine
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Sheet 1: Users
            users_data = []
            for u in users:
                users_data.append({
                    "User ID": u.id,
                    "Name": u.name,
                    "Email": u.email,
                    "Role": u.role,
                    "Registration Date": u.created_at.strftime("%Y-%m-%d %H:%M:%S") if u.created_at else ""
                })
            df_users = pd.DataFrame(users_data) if users_data else pd.DataFrame(columns=["User ID", "Name", "Email", "Role", "Registration Date"])
            df_users.to_excel(writer, sheet_name="Users", index=False)
            
            # Sheet 2: Queries
            queries_data = []
            for q in queries:
                username = q.user.name if q.user else "Unknown"
                district_name = q.district.district_name if q.district else "N/A"
                queries_data.append({
                    "Query ID": q.id,
                    "User ID": q.user_id,
                    "Username": username,
                    "Query": q.query,
                    "AI Response": q.response,
                    "District": district_name,
                    "Date": q.created_at.strftime("%Y-%m-%d") if q.created_at else "",
                    "Time": q.created_at.strftime("%H:%M:%S") if q.created_at else ""
                })
            df_queries = pd.DataFrame(queries_data) if queries_data else pd.DataFrame(columns=["Query ID", "User ID", "Username", "Query", "AI Response", "District", "Date", "Time"])
            df_queries.to_excel(writer, sheet_name="Queries", index=False)
            
            # Sheet 3: District Access
            access_data = []
            for a in accesses:
                last_acc = a.get("last_accessed")
                last_acc_str = last_acc.strftime("%Y-%m-%d %H:%M:%S") if last_acc else "N/A"
                access_data.append({
                    "District": a.get("district_name"),
                    "Total Views": a.get("total_views", 0),
                    "Unique Users": a.get("unique_users", 0),
                    "Last Accessed": last_acc_str
                })
            df_access = pd.DataFrame(access_data) if access_data else pd.DataFrame(columns=["District", "Total Views", "Unique Users", "Last Accessed"])
            df_access.to_excel(writer, sheet_name="District Access", index=False)
            
            # Sheet 4: Summary
            summary_data = [
                {"Metric": "Total Users", "Value": summary_stats.get("total_users", 0)},
                {"Metric": "Total Queries", "Value": summary_stats.get("total_queries", 0)},
                {"Metric": "Total Districts", "Value": summary_stats.get("total_districts", 0)},
                {"Metric": "Most Accessed District", "Value": summary_stats.get("most_viewed_district", "None")},
                {"Metric": "Average Queries Per User", "Value": round(summary_stats.get("avg_queries_per_user", 0.0), 2)}
            ]
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name="Summary", index=False)
            
        buffer.seek(0)
        return buffer
