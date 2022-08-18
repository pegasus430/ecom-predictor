from copy import deepcopy
from datetime import date
from datetime import datetime
from lxml import etree
import os
import re
from string import ascii_uppercase
from zipfile import ZIP_DEFLATED
from zipfile import ZipFile


class XlsxPatch(object):
    """
    Patch xmls inside an xlsx to fill cells.
    Should keep formatting.
    Limitations:
    * New row is added as a duplicate of the last one if needed.
      This also duplicates values and formatting.
    * Missed cell is appended to the end of the row.
    """

    _row_finder = re.compile(r'\d+$')
    _namespaces = {
        'ws': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
        'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'
    }

    def __init__(self, file):
        """
        Open document.
        File can be either a path to a file (a string) or a file-like object.
        """

        self._file = ZipFile(file)
        self._data = {}
        self._sheet = None
        self._sheet_paths = self._get_sheet_locations()
        self._shared_strings = self._get_xml('xl/sharedStrings.xml')
        self._shared_strings_root = self._shared_strings.xpath('/ws:sst', namespaces=self._namespaces)[0]
        self._shared_strings_index = int(self._shared_strings_root.attrib['uniqueCount'])

    def get_sheet_by_name(self, name):
        """Select sheet to patch"""

        if name in self._sheet_paths:
            self._sheet = name
            return self
        raise KeyError("Worksheet {0} does not exist.".format(name))

    def write(self, row, column, value):
        """
        Write a value.
        Row and column start with 1.
        """

        if value is not None and type(value) not in (int, float, str, unicode,
                                                     date, datetime):
            raise TypeError('Only None, int, float, str, unicode')
        if self._sheet not in self._data:
            self._data[self._sheet] = {}
        column -= 1
        cell = ascii_uppercase[column % 26] + str(row)
        while column >= 26:
            column = column // 26 - 1
            cell = ascii_uppercase[column % 26] + cell
        self._data[self._sheet][cell] = value

    def save(self, file):
        """
        Save document.
        File can be either a path to a file (a string) or a file-like object.
        """
        exclude_files = {e[1] for e in self._sheet_paths.items()
                         if e[0] in self._data.keys()}
        exclude_files.add('xl/sharedStrings.xml')
        zip_file = self._create_base_zip(file, exclude_files)
        self._add_changes(zip_file)
        zip_file.writestr('xl/sharedStrings.xml',
                          etree.tostring(self._shared_strings,
                                         xml_declaration=True,
                                         encoding="UTF-8",
                                         standalone="yes"))
        zip_file.close()

    def _get_xml(self, file_name):
        return etree.fromstring(self._file.read(file_name))

    def _get_sheet_locations(self):
        sheets_id = {}
        workbook_xml = self._get_xml('xl/workbook.xml')
        for sheet_xml in workbook_xml.xpath('/ws:workbook/ws:sheets/ws:sheet',
                                            namespaces=self._namespaces):
            sheet_name = sheet_xml.attrib['name']
            id_key = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            sheet_rid = sheet_xml.attrib[id_key]
            sheets_id[sheet_rid] = sheet_name
        paths = {}
        xml = self._get_xml('xl/_rels/workbook.xml.rels')
        for node in xml.xpath('/rel:Relationships/rel:Relationship',
                              namespaces=self._namespaces):
            r_id = node.attrib['Id']
            path = os.path.join('xl', node.attrib['Target'])
            if r_id in sheets_id:
                sheet_label = sheets_id[r_id]
                paths[sheet_label] = path
        return paths

    def _create_base_zip(self, file, exclude_files):
        zip_file = ZipFile(file, mode='w', compression=ZIP_DEFLATED)
        for file_name in self._file.namelist():
            if file_name not in exclude_files:
                zip_file.writestr(file_name, self._file.read(file_name))
        return zip_file

    def _add_shared_string(self, value):
        node_t = etree.Element('t')
        node_t.text = value
        node_si = etree.Element('si')
        node_si.append(node_t)
        self._shared_strings_root.append(node_si)
        self._shared_strings_index += 1
        self._shared_strings_root.attrib['uniqueCount'] = str(self._shared_strings_index)
        return self._shared_strings_index - 1

    def _add_row(self, xml):
        row_index = self._last_row.attrib['r']
        self._last_row_index = self._last_row_index + 1
        self._last_row.attrib['r'] = str(self._last_row_index)
        dimension = xml.xpath('/ws:worksheet/ws:dimension', namespaces=self._namespaces)[0]
        if ':' in dimension.attrib.get('ref'):
            dimension.attrib['ref'] = dimension.attrib['ref'][:-len(row_index)] + self._last_row.attrib['r']
        for node in self._last_row:
            if node.tag.endswith('}c') and 'r' in node.attrib and node.attrib['r'].endswith(row_index):
                cell = node.attrib['r'][:-len(row_index)] + self._last_row.attrib['r']
                node_f = node.find('ws:f', namespaces=self._namespaces)
                if node_f is not None and 'si' in node_f.attrib:
                    if 'ref' in node_f:
                        del node_f.attrib['ref']
                    pattern = '/ws:worksheet/ws:sheetData/ws:row/ws:c/ws:f[@si="%s"]' % node_f.attrib['si']
                    ref_node = xml.xpath(pattern, namespaces=self._namespaces)[0]
                    ref = ref_node.attrib.get('ref')
                    if ref:
                        if ':' in ref:
                            ref_node.attrib['ref'] = ref.split(':')[0] + ':' + cell
                        else:
                            ref_node.attrib['ref'] += ':' + cell
                node.attrib['r'] = cell
        parent = xml.xpath('/ws:worksheet/ws:sheetData', namespaces=self._namespaces)[0]
        parent.append(self._last_row)
        self._last_row = deepcopy(self._last_row)

    def _add_cell(self, xml, row_index, cell):
        pattern = '/ws:worksheet/ws:sheetData/ws:row[@r="%s"]' % row_index
        parent = xml.xpath(pattern, namespaces=self._namespaces)[0]
        node_c = etree.Element('c')
        node_c.attrib['r'] = cell
        parent.append(node_c)
        return node_c

    def _change_cell(self, xml, cell, value):
        row_index = int(self._row_finder.search(cell).group())
        while row_index > self._last_row_index:
            self._add_row(xml)
        value_type = type(value)
        pattern_params = {'row_index': row_index, 'cell': cell}
        pattern = '/ws:worksheet/ws:sheetData/ws:row[@r="%(row_index)s"]/ws:c[@r="%(cell)s"]' % pattern_params
        cells = xml.xpath(pattern, namespaces=self._namespaces)
        if cells:
            node_c = cells[0]
        else:
            node_c = self._add_cell(xml, row_index, cell)
        node_v = node_c.find('ws:v', namespaces=self._namespaces)
        if node_v is None:
            node_v = etree.Element('v')
            node_c.append(node_v)
        if value is None:
            node_c.remove(node_v)
            if node_c.attrib.get('t') == 's':
                del node_c.attrib['t']
        elif value_type in (unicode, str):
            value = str(self._add_shared_string(value))
            node_c.attrib['t'] = 's'
        else:
            if node_c.attrib.get('t') == 's':
                del node_c.attrib['t']
            if value_type == datetime:
                value = value.date()
            if value_type == date:
                value = (value - date(1899, 12, 30)).days
        node_v.text = unicode(value)

    def _get_changed_sheet(self, sheet_file, data):
        xml = self._get_xml(sheet_file)
        self._last_row = deepcopy(xml.xpath('/ws:worksheet/ws:sheetData/ws:row',
                                            namespaces=self._namespaces)[-1])
        self._last_row_index = int(self._last_row.attrib['r'])
        for cell, value in data.items():
            self._change_cell(xml, cell, value)
        return etree.tostring(xml, xml_declaration=True, encoding="UTF-8",
                              standalone="yes")

    def _add_changes(self, zip_file):
        for sheet_name, data in self._data.items():
            sheet_file = self._sheet_paths[sheet_name]
            sheet_content = self._get_changed_sheet(sheet_file, data)
            zip_file.writestr(sheet_file, sheet_content)
