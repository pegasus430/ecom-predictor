from cx_Freeze import setup, Executable

# To build standalone executable, run: python setup.py build

includes = [
    'idna.idnadata',
    'xlwt.ExcelFormulaParser',
    'xlwt.ExcelFormulaLexer',
]

buildOptions = dict(packages=[], excludes=[], includes=includes, include_msvcr=True)

base = 'Console'

executables = [
    Executable('download.py', base=base)
]

setup(name='download',
      version='1.0',
      description='Download the report.',
      options=dict(build_exe=buildOptions),
      executables=executables)
