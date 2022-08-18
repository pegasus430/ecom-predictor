import csv
import xlrd
import os
import openpyxl


class FileReader(object):

    @staticmethod
    def read(fp):
        ext = os.path.splitext(fp.filename)[-1].lower()

        if ext == '.csv':
            reader = FileReader._csv_reader
        elif ext == '.xls':
            reader = FileReader._xls_reader
        elif ext == '.xlsx':
            reader = FileReader._xlsx_reader
        else:
            raise Exception('Not supporting file type {}'.format(ext))

        return reader(fp)

    @staticmethod
    def _csv_reader(fp):
        rows = csv.reader(fp)

        header = [cell.strip().lower() for cell in rows.next()]

        for row in rows:
            row_dict = dict(zip(header, row))

            if row_dict:
                yield row_dict

    @staticmethod
    def _xls_reader(fp):
        workbook = xlrd.open_workbook(file_contents=fp.read())
        sheet = workbook.sheet_by_index(0)

        rows = sheet.get_rows()
        header = [cell.value.strip().lower() for cell in rows.next()]

        for row in rows:
            row_dict = dict(zip(header, (cell.value for cell in row)))

            if row_dict:
                yield row_dict

    @staticmethod
    def _xlsx_reader(fp):
        workbook = openpyxl.load_workbook(fp)
        sheet = workbook.get_active_sheet()

        rows = sheet.rows
        header = [cell.value.strip().lower() for cell in rows.next()]

        for row in rows:
            row_dict = dict(zip(header, (cell.value for cell in row)))

            if row_dict:
                yield row_dict
