import tkinter as tk
from tkinter import ttk, messagebox
import dbf
import shutil
import os
from os import path
import sys
from datetime import datetime
import ctypes

# 1. High-DPI Awareness (Fix jagged/blurry text on Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

DBF_FOLDER_NAME = "DAGA"
DBF_NAME= "DAGA.DBF"
DBF_BACKUP_NAME = "DAGA_BACKUP.DBF"

# DBF_PATH = "DAGA/DAGA.DBF"
# BACKUP_PATH = "DAGA/DAGA.DBF.bak"
ENCODING = 'cp950'

class SetupFilePath(object):
    def __init__(self):
        super(SetupFilePath, self).__init__()
        self.root_path = sys.path[0]
        self.dbf_folder_name = ''
        self.dbf_path = ''
        self.dbf_backup_path = ''
        self.path_ready = False

        self.find_root_path()
        self.set_all_path()

    def find_root_path(self):
        root_path_find = False

        for retry_count in range(1, 6):
            self.dbf_folder_name = path.join(self.root_path, DBF_FOLDER_NAME)
            # print(self.dbf_folder_name)
            if path.exists(self.dbf_folder_name):
                root_path_find = True
                break
            else:
                self.root_path = path.join(self.root_path, '..')

        if not root_path_find:
            messagebox.showerror("開啟錯誤", f"無法讀取目錄: {DBF_FOLDER_NAME}")
            raise

        self.root_path = path.realpath(self.root_path)

    def set_all_path(self):
        self.dbf_path = path.join(self.dbf_folder_name, DBF_NAME)
        if not path.exists(self.dbf_path):
            messagebox.showerror("開啟錯誤", f"無法讀取DBF: {self.dbf_path}")
            raise

        file_name = os.path.basename(DBF_BACKUP_NAME)
        name, ext = os.path.splitext(file_name)
        dbf_back_name='{}_{}{}'.format(name, datetime.now().strftime("%Y%m%d%H%M%S"), ext)
        self.dbf_backup_path = path.join(self.root_path, dbf_back_name)


class DBFEditorApp(SetupFilePath):
    def __init__(self, root):
        super(DBFEditorApp, self).__init__()
        # Data State
        self.current_record = None
        self.field_entries = {}
        self.field_names = []
        self.current_table = None
        
        self.root = root
        self.root.title("DAGA 進銷存資料編輯器")
        self.root.geometry("1200x800")
        # self.root.iconbitmap("dbf_editor.ico")
        
        if not self.load_table_info():
            raise

        # Apply Theme
        style = ttk.Style()
        try:
            style.theme_use('vista')  # Try Windows native theme
        except:
            style.theme_use('clam')   # Fallback

        # Configure styles
        style.configure('TLabel', font=('Microsoft JhengHei', 10))
        style.configure('TButton', font=('Microsoft JhengHei', 10))
        style.configure('TEntry', font=('Microsoft JhengHei', 10))
        
        # Header/Search Frame
        search_frame = ttk.Labelframe(root, text="搜尋操作", padding=15)
        search_frame.pack(fill=tk.X, padx=15, pady=10)
        
        ttk.Label(search_frame, text="請輸入櫃號 (第一欄):").pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        entry.pack(side=tk.LEFT, padx=5)
        entry.bind('<Return>', lambda e: self.search_record())
        entry.focus_set()
        
        btn_search = ttk.Button(search_frame, text="🔍 搜尋", command=self.search_record)
        btn_search.pack(side=tk.LEFT, padx=10)
        
        btn_save = ttk.Button(search_frame, text="💾 儲存修改", command=self.save_record)
        btn_save.pack(side=tk.LEFT, padx=10)

        # Status Bar
        self.status = ttk.Label(root, text="就緒 - 請輸入編號搜尋", relief=tk.SUNKEN, anchor=tk.W)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

        # Main Content Area (Scrollable)
        self.fields_frame = ttk.LabelFrame(root, text="資料內容 (可直接修改)", padding=5)
        self.fields_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)
        
        self.canvas = tk.Canvas(self.fields_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.fields_frame, orient="vertical", command=self.canvas.yview)
        
        # Inner Scrollable Frame
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Initialize
        root.deiconify()
        self.backup_dbf()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def backup_dbf(self):
        if os.path.exists(self.dbf_path) and not os.path.exists(self.dbf_backup_path):
            try:
                shutil.copy2(self.dbf_path, self.dbf_backup_path)
                self.status.config(text=f"備份成功: {self.dbf_backup_path}")
            except Exception as e:
                messagebox.showerror("備份失敗", str(e))

    def load_table_info(self):
        try:
            with dbf.Table(self.dbf_path, codepage=ENCODING) as table:
                self.field_names = table.field_names
        except Exception as e:
            messagebox.showerror("開啟錯誤", f"無法讀取 DBF: {e}")
            return False
        return True

    def search_record(self):
        query = self.search_var.get().strip()
        if not query:
            return

        self.clear_fields()
        found = False
        
        try:
            if self.current_table:
                try: self.current_table.close()
                except: pass

            self.current_table = dbf.Table(self.dbf_path, codepage=ENCODING)
            self.current_table.open(mode=dbf.READ_WRITE)
            
            target_field = self.field_names[0]
            
            self.status.config(text="搜尋中...")
            self.root.update()

            # Index search first
            try:
                index = self.current_table.create_index(lambda rec: (rec[target_field]))
                match = index.search(match=query, partial=False)
                if match:
                    self.current_record = match[0]
                    self.populate_fields(self.current_record)
                    self.status.config(text=f"✅ 找到資料: {query}")
                    found = True
            except:
                # Fallback to linear scan
                pass

            if not found:
                for record in self.current_table:
                    val = str(record[target_field]).strip()
                    if val == query:
                        self.current_record = record
                        self.populate_fields(record)
                        self.status.config(text=f"✅ 找到資料: {query}")
                        found = True
                        break
            
            if not found:
                self.status.config(text=f"❌ 找不到: {query}")
                messagebox.showinfo("搜尋結果", "找不到該筆資料")
                self.current_table.close()
                self.current_table = None

        except Exception as e:
            messagebox.showerror("搜尋錯誤", str(e))
            if self.current_table:
                self.current_table.close()
                self.current_table = None

    def clear_fields(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.field_entries = {}
        self.current_record = None

    def populate_fields(self, record):
        r = 0
        for field in self.field_names:
            val = record[field]
            if isinstance(val, str):
                val = val.strip()
            
            # Use alternating row colors or distinct label style
            ttk.Label(self.scrollable_frame, text=field, width=20, anchor='e').grid(row=r, column=0, padx=10, pady=5, sticky='e')
            
            entry = ttk.Entry(self.scrollable_frame, width=50)
            entry.insert(0, str(val))
            entry.grid(row=r, column=1, padx=10, pady=5, sticky='w')
            
            self.field_entries[field] = entry
            r += 1

    def save_record(self):
        if not self.current_record or not self.current_table:
            messagebox.showwarning("警告", "沒有選中的資料可儲存")
            return

        try:
            with self.current_record as rec:
                changes_made = False
                for field, entry in self.field_entries.items():
                    new_val = entry.get()
                    old_val = rec[field]
                    
                    if str(old_val).strip() != new_val.strip():
                        rec[field] = new_val
                        changes_made = True
                
            if changes_made:
                self.status.config(text="✅ 資料已儲存")
                messagebox.showinfo("成功", "資料已更新！\n請記得執行索引重整。")
            else:
                self.status.config(text="⚠️ 未偵測到變更")

        except Exception as e:
            messagebox.showerror("儲存失敗", str(e))

    def __del__(self):
        if self.current_table:
            try: self.current_table.close()
            except: pass

if __name__ == "__main__":
    tk_root = tk.Tk()
    tk_root.iconphoto(True, tk.PhotoImage(file="dbf_editor.png"))
    tk_root.withdraw()
    app = DBFEditorApp(tk_root)
    tk_root.mainloop()
