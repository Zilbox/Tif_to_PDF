import os
from pathlib import Path
import time
import img2pdf
from PIL import Image
import tkinter as tk
from tkinter import filedialog, scrolledtext, Checkbutton, BooleanVar
import sys
import threading


# Класс для перенаправления вывода print() в текстовое поле
# ----------------------------------------------------------------------
class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        # Вставляем текст в конец виджета и прокручиваем вниз
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)
        self.text_widget.update_idletasks()

    def flush(self):
        # Необходимо для совместимости с sys.stdout
        pass


# Класс главного окна
# ----------------------------------------------------------------------
class App:
    def __init__(self, root):
        self.root = root
        root.title("Конвертор tif в pdf")

        # Переменные для хранения путей
        self.path_file_or_folder = tk.StringVar()
        self.path_folder = tk.StringVar()

        # Переменная для выбора папка - файл
        self.radio_var = tk.IntVar()
        self.radio_var.set(1)

        # Фрейм-контейнер
        frame = tk.Frame(root)
        frame.grid(row=0, column=0, sticky="ew")

        # ---------- Элементы интерфейса ----------
        # 1) Выбор пути к папке с tif
        rad1 = tk.Radiobutton(frame, text="Выбор папки tif", variable=self.radio_var, value=1)
        rad2 = tk.Radiobutton(frame, text="Выбор файла tif", variable=self.radio_var, value=2)
        rad1.pack(side="left", padx=5)
        rad2.pack(side="left", fill="x", expand=True)
        entry1 = tk.Entry(root, textvariable=self.path_file_or_folder, width=50)
        entry1.grid(row=0, column=1, padx=5, pady=5)
        btn1 = tk.Button(root, text="Обзор...", command=self.browse_tif_source)
        btn1.grid(row=0, column=2, padx=5, pady=5)

        # 2) Выбор пути к папке куда сохранять
        tk.Label(root, text="Путь к папке куда сохранять:").grid(row=1, column=0, sticky='w', padx=5, pady=5)
        entry2 = tk.Entry(root, textvariable=self.path_folder, width=50)
        entry2.grid(row=1, column=1, padx=0, pady=0)
        btn2 = tk.Button(root, text="Обзор...", command=self.browse_output_folder)
        btn2.grid(row=1, column=2, padx=5, pady=5)

        # 5) Кнопка запуска
        btn_run = tk.Button(root, text="Запустить конвертирование", command=self.start_processing)
        btn_run.grid(row=2, column=0, columnspan=3, pady=10)

        # 6) Область вывода текста (скроллируемое текстовое поле)
        self.output_text = scrolledtext.ScrolledText(root, width=80, height=10, state='normal')
        self.output_text.grid(row=3, column=0, columnspan=3, padx=5, pady=5)

        # Перенаправление sys.stdout в виджет
        self.redirector = PrintRedirector(self.output_text)
        sys.stdout = self.redirector

        # Перенаправление sys.stderr (ошибки):
        sys.stderr = self.redirector

    # ---------- Методы для выбора путей ----------
    def browse_tif_source(self):
        if self.radio_var.get() == 1:
            path = filedialog.askdirectory(title="Выберите папку с TIF-файлами")
        else:
            path = filedialog.askopenfilename(title="Выберите TIF-файл")
        if path:
            self.path_file_or_folder.set(path)

    def browse_output_folder(self):
        path = filedialog.askdirectory(title="Выберите папку для сохранения PDF")
        if path:
            self.path_folder.set(path)

    # ---------- Запуск обработки в отдельном потоке ----------
    def start_processing(self):
        # Очищаем вывод перед новым запуском
        self.output_text.delete(1.0, tk.END)

        # Получаем значения
        path1 = self.path_file_or_folder.get().strip()
        path2 = self.path_folder.get().strip()

        # Проверка всех полей
        if not path1 or not path2:
            print("Ошибка: не выбраны все пути!")
            return

        # Запускаем основную логику в отдельном потоке, чтобы GUI не зависал
        thread = threading.Thread(target=copy_tif, args=(path1, path2))
        thread.daemon = True
        thread.start()


# Основная функция программы
def copy_tif(source_root: str, output_root: str):
    print("-----КОНВЕРТАЦИЯ НАЧАЛАСЬ-----")
    sours_tif = Path(source_root) # Путь к папке с tif
    output = Path(output_root) # Путь куда сохранять результат
    use_rel_path = True

    # Cбор путей .tif
    # ------------------------------------------------------------
    tif_files = []
    print("-----СБОР TIFF ФАЙЛОВ-----")
    if app.radio_var.get() == 2:
        tif_files = [sours_tif]
        use_rel_path = False
    else:
        files_num = 0
        for current_dir, _, files in os.walk(Path(sours_tif)):
            for fname in files:
                for attempt in range(3):  # 3 попытки
                    try:
                        full_path = Path(current_dir) / fname
                        ext = full_path.suffix.lower()
                        if ext in ('.tif', '.tiff'):
                            files_num += 1
                            if files_num % 100 == 0:
                                print('Найдено tif: ', files_num)
                            tif_files.append(full_path)
                        break
                    except OSError as e:
                        if e.winerror == 64:
                            print(f"Сетевая ошибка, попытка {attempt + 1}...")
                            time.sleep(2)  # подождать 2 секунды
                        else:
                            raise

    tif_nums = len(tif_files)

    # Копируем и конвертируем в PDF
    # ------------------------------------------------------------
    id_copy = 0
    Image.MAX_IMAGE_PIXELS = None
    for tif_path in tif_files:
        for attempt in range(3):  # 3 попытки
            try:
                try:
                    # Получаем путь относительно исходной корневой папки
                    rel_path = tif_path.relative_to(source_root)
                except ValueError:
                    print(f"Файл {tif_path} не находится внутри {source_root}, пропускаем.")
                    continue

                # Исходное имя файла без расширения
                base_name = tif_path.stem
                # Запрещённые символы Windows
                translation_table = str.maketrans("", "", r'[<>:"/\|?*]')
                new_base_name = base_name.translate(translation_table)
                # Целевой путь PDF
                if use_rel_path:
                    rel_path = tif_path.relative_to(source_root)
                    pdf_rel_path = rel_path.with_name(new_base_name + ".pdf")
                else:
                    pdf_rel_path = Path(new_base_name + ".pdf")
                dest_path = output / pdf_rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)

                # Конвертация TIFF в PDF
                for attempt in range(3):  # 3 попытки при сетевых ошибках
                    try:
                        pdf_bytes = img2pdf.convert(str(tif_path))
                        dest_path.write_bytes(pdf_bytes)
                        print(f"Конвертирован: {tif_path} → {dest_path}")
                        id_copy += 1
                        break
                    except OSError as e:
                        if hasattr(e, 'winerror') and e.winerror == 64:
                            print(f"Сетевая ошибка, попытка {attempt + 1}...")
                            time.sleep(2)
                        else:
                            print(f"Ошибка при конвертации {tif_path}: {e}")
                            break
                    except Exception as e:
                        print(f"Ошибка при конвертации {tif_path}: {e}")
                        break

                break

            except OSError as e:
                if e.winerror == 64:
                    print(f"Сетевая ошибка, попытка {attempt + 1}...")
                    time.sleep(2)  # подождать 2 секунды
                else:
                    raise

    print(f"Готово. Всего было tif-файлов - {tif_nums}. Перенесено - {id_copy}.")
    print("-----КОНВЕРТАЦИЯ ЗАВЕРШЕНА-----")


if __name__ == '__main__':
    root = tk.Tk()
    app = App(root)
    root.mainloop()