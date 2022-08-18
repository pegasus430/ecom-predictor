#!/usr/bin/python

# Split a file of URLs into smaller files
# Run "python split_urls_file.py -h" to get help on usage

from optparse import OptionParser
import re

def extract_filename_and_extension(filename):
    # remove directory name if any, extract file name and extension (if any)
    m = re.match("(.*/)?([^/]*)\.((txt)|(csv))", filename)
    if m:
        base = m.group(2)
        if m.group(3):
            extension = "." + m.group(3)
    else:
        # try without extension
        m = re.match("(.*/)?([^/]*)", filename)
        if m:
            # default extension is .txt
            base = m.group(2)
            extension = ".txt"
        else:
            base = filename
            extension = ".txt"

    return (base, extension)

def generate_outfilename(base, number, extension):
    return base + "_" + str(number) + extension

# main method
def split():
    parser = OptionParser()
    parser.add_option("--infile", "-f", dest="in_filename",
                      help="Input file")

    parser.add_option("--outfile", "-o", dest="out_filename",
                      help="Output file name")

    parser.add_option("--batch_size", "-s", dest="batch_size",
                      help="Number of rows in each output file", default=250)

    parser.add_option("--with_header", "-r", dest="with_header",
                      help="Include header row from input in all output files? (1/0)", default=1)

    (options, args) = parser.parse_args()

    # extract base of output files names from filename given as an argument
    # by default use input file's name to generate output files names; otherwise use the one provided as an argument
    if not options.out_filename:
        options.out_filename = options.in_filename
    (outfiles_base, outfiles_extension) = extract_filename_and_extension(options.out_filename)

    infile = open(options.in_filename, "r")

    # output files
    outfiles = []

    if int(options.with_header):
        header_line = infile.readline()

    # current output file
    outfile_nr = 1
    outfilename = generate_outfilename(outfiles_base, outfile_nr, outfiles_extension)
    outfile = open(outfilename, "w")
    if int(options.with_header):
        outfile.write(header_line)


    # append current file to output files list
    outfiles.append(outfile)

    lines = 1

    for line in infile:

        outfile.write(line)

        # number of lines in current output file
        lines += 1

        if lines > int(options.batch_size):
            # reset line count
            lines = 1

            # open next file
            outfile_nr += 1
            outfilename = generate_outfilename(outfiles_base, outfile_nr, outfiles_extension)
            outfile = open(outfilename, "w")

            if int(options.with_header):
                outfile.write(header_line)


    # close all open files
    infile.close()
    for f in outfiles:
        f.close()


if __name__=="__main__":
    split()
