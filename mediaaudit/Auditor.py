import KohlsAudit
import MacysAudit
import JCPenneyAudit
import Convert


def initialize(website, input, output):
    if website == 'Kohls':
        KohlsAudit.run(input, output)
    elif website == 'Macys':
        MacysAudit.run(input, output)
    elif website == 'JCPenny':
        JCPenneyAudit.run(input, output)


def convert(input, output):
    Convert.run(input, output)
