#!/usr/bin/env python3

# Runepub - A tool for fetching Runeberg books and building epub files.
# Copyright 2018 Kristian Rumberg (kristianrumberg@gmail.com)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to who#m the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.

from enum import Enum
from dataclasses import dataclass

import argparse
import os
import shutil
import zipfile
from io import StringIO
from pathlib import Path
import requests

HOST = "http://runeberg.org"

RUNEDIR = os.path.join(str(Path.home()), ".runepub")

@dataclass
class DownloadItem:
    url: str
    zip_filename: str


def _get_download_items(bookname):
    return [
        DownloadItem("{}/download.pl?mode=txtzip&work={}".format(HOST,
                                                                 bookname),
                     "txt.zip"),
        #DownloadItem("{}/{}.zip".format(HOST, bookname), "images.zip")
    ]

def _get_temp_dir(bookname):
    return os.path.join(RUNEDIR, bookname, "temp")


def _get_downloaded_dir(bookname):
    return os.path.join(RUNEDIR, bookname, "downloaded")


def _get_unpack_dir(bookname):
    return os.path.join(RUNEDIR, bookname, "unpacked")


def _get_build_dir(bookname):
    return os.path.join(RUNEDIR, bookname, "build")


def download(bookname):
    temp_dir = _get_temp_dir(bookname)

    items = _get_download_items(bookname)

    for item in items:
        url = item.url
        zip_filename = item.zip_filename

        downloaded_dir = _get_downloaded_dir(bookname)
        downloadedpath = os.path.join(downloaded_dir, zip_filename)

        if os.path.isfile(downloadedpath):
            continue

        if not os.path.isdir(temp_dir):
            os.makedirs(temp_dir)

        temp_out_zippath = os.path.join(temp_dir, zip_filename)

        r = requests.get(url, stream=True)
        if r.status_code == 200:
            with open(temp_out_zippath, 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)


        if not os.path.isdir(downloaded_dir):
            os.makedirs(downloaded_dir)

        shutil.move(temp_out_zippath, downloadedpath)

    try:
        os.rmdir(temp_dir)
    except OSError:
        pass


def unpack(bookname):
    unpack_dir = _get_unpack_dir(bookname)

    if os.path.isdir(unpack_dir):
        shutil.rmtree(unpack_dir)
    os.makedirs(unpack_dir)

    items = _get_download_items(bookname)
    for item in items:
        downloaded_path = os.path.join(_get_downloaded_dir(bookname),
                                       item.zip_filename)

        with zipfile.ZipFile(downloaded_path, 'r') as zfile:
            zfile.extractall(unpack_dir)


class ChapterType(Enum):
    INDEX = 1
    REGULAR = 2


class RuneChapter:
    def __init__(self, type, index, title, ranges):
        self._type = type
        self._index = index
        self._title = title
        self._ranges = ranges

    def type(self):
        return self._type

    def index(self):
        return self._index

    def title(self):
        return self._title

    def ranges(self):
        return self._ranges


class EPubChapter:
    def __init__(self, type, index, title):
        self._type = type
        self._index = index
        self._title = title

    def type(self):
        return self._type

    def index(self):
        return self._index

    def id(self):
        return "chapter{0:04d}".format(self.index())

    def title(self):
        return self._title

    def filename(self):
        return self.id() + ".xhtml"


class EpubWriter:
    def __enter__(self):
        return self


    def __init__(self, build_dir, author, title):
        self.chapters = []

        self.book_ncx = None
        self.book_opf = None

        self.build_dir = build_dir

        os.makedirs(os.path.join(self.build_dir, "OEBPS"))
        os.makedirs(os.path.join(self.build_dir, "META-INF"))

        with open(os.path.join(self.build_dir, "mimetype"), "wt") as stream:
            stream.write("application/epub+zip")
            stream.flush()

        with open(os.path.join(self.build_dir, "META-INF", "container.xml"), "wt") as stream:
            stream.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>" + "\n")
            stream.write("<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">" + "\n")
            stream.write("<rootfiles>" + "\n")
            stream.write("<rootfile full-path=\"OEBPS/book.opf\" media-type=\"application/oebps-package+xml\"/>" + "\n")
            stream.write("</rootfiles>" + "\n")
            stream.write("</container>" + "\n")
            stream.flush()

        self.book_opf = open(os.path.join(self.build_dir, "OEBPS", "book.opf"), "wt")
        self.book_opf.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>" + "\n")
        self.book_opf.write("<package version=\"2.0\" xmlns=\"http://www.idpf.org/2007/opf\"" + "\n")
        self.book_opf.write("	 unique-identifier=\"abcdef\">" + "\n")
        self.book_opf.write("  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\"" + "\n")
        self.book_opf.write("	    xmlns:opf=\"http://www.idpf.org/2007/opf\">" + "\n")
        self.book_opf.write(("    <dc:title>{}</dc:title>" + "\n").format(title))
        self.book_opf.write(("    <dc:creator opf:role=\"aut\">{}</dc:creator>" + "\n").format(author))
        self.book_opf.write("    <dc:language>en-US</dc:language>" + "\n")
        self.book_opf.write("    <dc:identifier id=\"abcdef\">abcdef</dc:identifier>" + "\n")
        self.book_opf.write("  </metadata>" + "\n")
        self.book_opf.write("  <manifest>" + "\n")

        self.book_ncx = open(os.path.join(self.build_dir, "OEBPS", "book.ncx"), "wt")
        self.book_ncx.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>" + "\n")
        self.book_ncx.write("<ncx version=\"2005-1\" xml:lang=\"en\" xmlns=\"http://www.daisy.org/z3986/2005/ncx/\">" + "\n")
        self.book_ncx.write("  <head>" + "\n")
        self.book_ncx.write("    <meta name=\"dtb:uid\" content=\"abcdef\" />" + "\n")
        self.book_ncx.write("    <meta name=\"dtb:depth\" content=\"1\" />" + "\n")
        self.book_ncx.write("    <meta name=\"dtb:totalPageCount\" content=\"0\" />" + "\n")
        self.book_ncx.write("    <meta name=\"dtb:maxPageNumber\" content=\"0\" />" + "\n")
        self.book_ncx.write("  </head>" + "\n")
        self.book_ncx.write("  <docTitle>" + "\n")
        self.book_ncx.write(("    <text>{}</text>" + "\n").format(title))
        self.book_ncx.write("  </docTitle>" + "\n")


    def add_chapter(self, chapter: EPubChapter):
        self.chapters.append(chapter)


    def __exit__(self, t, value, tb):
        if self.book_opf:
            for chapter in self.chapters:
                id = chapter.id()
                filename = chapter.filename()
                self.book_opf.write(("    <item id=\"{}\" href=\"{}\" media-type=\"application/xhtml+xml\" />" + "\n").format(id, filename))

            self.book_opf.write("    <item id=\"ncx\" href=\"book.ncx\" media-type=\"application/x-dtbncx+xml\" />" + "\n")
            self.book_opf.write("  </manifest>" + "\n")
            self.book_opf.write("  <spine toc=\"ncx\">" + "\n")

            for chapter in self.chapters:
                id = chapter.id()
                self.book_opf.write(("    <itemref idref=\"{}\" />" + "\n").format(id))

            self.book_opf.write("  </spine>" + "\n")
            self.book_opf.write("</package>" + "\n")

        if self.book_ncx:
            self.book_ncx.write("  <navMap>" + "\n")
            for chapter in self.chapters:
                self.book_ncx.write("    <navPoint id=\"{}\" playOrder=\"{}\">\n".format(chapter.id(), chapter.index()))
                self.book_ncx.write("      <navLabel><text>{}</text></navLabel>\n".format(chapter.title()))
                self.book_ncx.write("      <content src=\"{}\"/>\n".format(chapter.filename()))
                self.book_ncx.write("    </navPoint>\n")
            self.book_ncx.write("  </navMap>" + "\n")
            self.book_ncx.write("</ncx>" + "\n")


def _parse_unpacked_metadata(bookname):
    unpacked_dir = _get_unpack_dir(bookname)

    with open(os.path.join(unpacked_dir, "Metadata"), "rt",
              encoding="latin-1") as stream:
        values = {}

        for line in stream:
            line = line.strip()
            if ":" in line:
                key, value = [x.strip() for x in line.split(":", 1)]
                values[key] = value

        return values

def _parse_unpacked_rune_chapters(bookname):
    unpacked_dir = _get_unpack_dir(bookname)

    with open(os.path.join(unpacked_dir, "Articles.lst"), "rt") as stream:
        values = []

        i = 0

        for line in stream:
            line = line.split("#")[0]
            line = line.strip()

            if not line:
                continue

            if "|" in line:
                type, title, rangeexpr = [x.strip() for x in line.split("|", 2)]

                if type == "":
                    type = ChapterType.REGULAR
                elif type == "index":
                    type = ChapterType.INDEX
                elif type == "-":
                    # Subchapters are covered inside chapters
                    continue
                else:
                    raise Exception("Unknown chapter definition {}".format(line))

                ranges = []
                for entry in rangeexpr.split():
                    if "-" in entry:
                        ranges.append([int(x) for x in entry.split("-")])
                    else:
                        ranges.append([int(entry)] * 2)

                values.append(RuneChapter(type, i, title, ranges))

                i += 1

        return values


def _unpacked_range_reader(bookname, ranges):
    unpacked_dir = _get_unpack_dir(bookname)

    for r in ranges:
        for index in range(r[0], r[1] + 1):
            path = os.path.join(unpacked_dir, "Pages", "{0:04d}.txt".format(index))
            with open(path, "rt") as stream:
                for line in stream:
                    line = line.strip()
                    yield line


def build_epub(bookname, author):
    build_dir = _get_build_dir(bookname)

    if os.path.isdir(build_dir):
        shutil.rmtree(build_dir)
    os.makedirs(build_dir)

    metadata = _parse_unpacked_metadata(bookname)

    title = metadata["TITLE"]

    with EpubWriter(build_dir, author=author, title=title) as epub_writer:
        rune_chapters = _parse_unpacked_rune_chapters(bookname)

        for rune_chapter in rune_chapters:
            epub_chapter = EPubChapter(rune_chapter.type(),
                                       rune_chapter.index(),
                                       rune_chapter.title())
            path = os.path.join(build_dir, "OEBPS",
                                epub_chapter.filename())

            with open(path, "wt") as out_stream:
                out_stream.write("<?xml version=\"1.0\" encoding=\"utf-8\"?>" + "\n")
                out_stream.write("<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.1//EN\" \"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd\">" + "\n")
                out_stream.write("<html xmlns=\"http://www.w3.org/1999/xhtml\" xml:lang=\"en\">" + "\n")
                out_stream.write("<head>" + "\n")
                out_stream.write("<meta http-equiv=\"Content-Type\" content=\"application/xhtml+xml; charset=utf-8\" />" + "\n")
                out_stream.write("</head>" + "\n")
                out_stream.write("\n")
                out_stream.write("<body>" + "\n")

                buff = StringIO()

                class ScopeState(Enum):
                    BEFORE = 1
                    WITHIN = 2
                    AFTER = 3

                state = ScopeState.BEFORE
                for line in _unpacked_range_reader(bookname, rune_chapter.ranges()):
                    if line.count("<") != line.count(">"):
                        line = line.replace("<", "")
                        line = line.replace(">", "")

                    if rune_chapter.type() == ChapterType.REGULAR:
                        if state == ScopeState.BEFORE:
                            if "<chapter" in line:
                                buff = StringIO()
                                state = ScopeState.WITHIN
                        elif state == ScopeState.WITHIN:
                            if "</chapter>" in line:
                                state = ScopeState.AFTER

                        if state != ScopeState.AFTER:
                            if not "<chapter" in line and not "</chapter>" in line:
                                buff.write(line + "\n")
                    elif rune_chapter.type() == ChapterType.INDEX:
                        out_stream.write(line + "\n")

                out_stream.write(buff.getvalue())

                out_stream.write("</body>" + "\n")
                out_stream.write("</html>" + "\n")

                out_stream.flush()

                epub_writer.add_chapter(epub_chapter)


def zip_epub(bookname):
    build_dir = _get_build_dir(bookname)
    epub_dir = "."

    if not os.path.isdir(epub_dir):
        os.makedirs(epub_dir)

    zip_outfile = os.path.join(epub_dir, bookname + ".epub")

    with  zipfile.ZipFile(zip_outfile, mode='w') as stream:
        build_dir_str_len = len(build_dir)
        for root, _, files in os.walk(build_dir):
            for f in files:
                file_path = os.path.join(root, f)
                stream.write(file_path, file_path[build_dir_str_len:])


def main():
    parser = argparse.ArgumentParser(description='Runepub - A tool for fetching Runeberg books and building epub files.')
    parser.add_argument("-i", "--id", required=True,
                        help="Book id")
    parser.add_argument("-a", "--author", required=True,
                        help="Book author")
    args = parser.parse_args()

    bookname = args.id
    author = args.author

    download(bookname)
    unpack(bookname)

    build_epub(bookname, author)

    zip_epub(bookname)

main()
