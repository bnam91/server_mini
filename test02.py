import tkinter as tk
from tkinter import messagebox
from datetime import datetime

# 루트 윈도우 생성 (숨김)
root = tk.Tk()
root.withdraw()

# 현재 시각 가져오기
current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 팝업 메시지 표시
messagebox.showinfo("Hello", f"Have a nice day!\n\nCurrent Time: {current_time}")

# 애플리케이션 종료
root.destroy()

