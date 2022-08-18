import smtplib
import glob
import xml.etree.ElementTree as ET

strBasePath = "/home/ubuntu/production/"
latest_git_file_path = glob.glob(strBasePath + "tmtext/special_crawler/*_version.xml")
old_git_file_path = glob.glob(strBasePath + "tmtext_old/special_crawler/*_version.xml")

latest_git_file_name = []

for path in latest_git_file_path:
    latest_git_file_name.append(path[path.rfind("/") + 1:])

old_git_file_name = []

for path in old_git_file_path:
    old_git_file_name.append(path[path.rfind("/") + 1:])

common_file_name = list(set(latest_git_file_name).intersection(old_git_file_name))
new_file_name = list(set(latest_git_file_name) - set(old_git_file_name))
removed_file_name = list(set(old_git_file_name) - set(latest_git_file_name))

report_results = ""

for scraper in new_file_name:

    scraper_results = ""

    scraper_version_xml = ET.parse(strBasePath + "tmtext/special_crawler/" + scraper)

    scraper_version_root = scraper_version_xml.getroot()

    scraper_version_field_names = []

    for field in scraper_version_root:
        scraper_version_field_names.append(field.attrib["name"])

    if scraper_version_field_names:
        scraper_results += ("\n- Fields Added \n" + ", " . join(scraper_version_field_names))

    report_results += ("New Scraper: " + scraper[8:-12] + scraper_results + "\n\n")

for scraper in removed_file_name:

    report_results += ("Removed Scraper: " + scraper[8:-12] + scraper_results + "\n\n")

for scraper in common_file_name:

    scraper_results = ""

    latest_scraper_version_xml = ET.parse(strBasePath + "tmtext/special_crawler/" + scraper)
    old_scraper_version_xml = ET.parse(strBasePath + "tmtext_old/special_crawler/" + scraper)

    latest_scraper_version_root = latest_scraper_version_xml.getroot()
    old_scraper_version_root = old_scraper_version_xml.getroot()

    latest_scraper_version_fields = {}
    old_scraper_version_fields = {}
    latest_scraper_version_field_names = []
    old_scraper_version_field_names = []
    scraper_version_common_field_names = []

    for field in latest_scraper_version_root:
        latest_scraper_version_fields[field.attrib["name"]] = field.attrib["version"]
        latest_scraper_version_field_names.append(field.attrib["name"])

    for field in old_scraper_version_root:
        old_scraper_version_fields[field.attrib["name"]] = field.attrib["version"]
        old_scraper_version_field_names.append(field.attrib["name"])

    scraper_version_common_field_names = list(set(latest_scraper_version_field_names).intersection(
        old_scraper_version_field_names))

    changed_fields = []

    for field_name in scraper_version_common_field_names:
        if latest_scraper_version_fields[field_name] != old_scraper_version_fields[field_name]:
            changed_fields.append(field_name)

    if changed_fields:
        scraper_results += ("\n- Fields Changed \n" + ", " . join(changed_fields))

    scraper_version_new_field_names = list(set(latest_scraper_version_field_names) - set(old_scraper_version_field_names))

    new_fields = []

    for field_name in scraper_version_new_field_names:
        new_fields.append(field_name)

    if new_fields:
        scraper_results += ("\n- Fields Added \n" + ", " . join(new_fields))

    scraper_version_old_field_names = list(set(old_scraper_version_field_names) - set(latest_scraper_version_field_names))

    removed_fields = []

    for field_name in scraper_version_old_field_names:
        removed_fields.append(field_name)

    if removed_fields:
        scraper_results += ("\n- Fields Removed \n" + ", " . join(removed_fields))

    if scraper_results:
        report_results += ("Updated Scraper: " + scraper[8:-12] + scraper_results + "\n\n")

if not report_results:
    exit(0)

print report_results

fromaddr = "jenkins@contentanalyticsinc.com"
toaddrs = ["dave@contentanalyticsinc.com", "support@contentanalyticsinc.com"] # must be a list
subject = "Production CH Scrapers Updated"
msg = """\
From: %s
To: %s
Subject: %s

%s
""" % (fromaddr, ", ".join(toaddrs), subject, report_results)

print "Message length is " + repr(len(msg))

#Change according to your settings
smtp_server = 'email-smtp.us-east-1.amazonaws.com'
smtp_username = 'AKIAI2XV5DZO5VTJ6LXQ'
smtp_password = 'AgWhl58LTqq36BpcFmKPs++24oz6DuS/J1k2GrAmp1T6'
smtp_port = '587'
smtp_do_tls = True

server = smtplib.SMTP(
    host = smtp_server,
    port = smtp_port,
    timeout = 10
)
server.set_debuglevel(10)
server.starttls()
server.ehlo()
server.login(smtp_username, smtp_password)
server.sendmail(fromaddr, toaddrs, msg)
print server.quit()
