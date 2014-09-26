#!/usr/bin/env python
#
# Copyright 2008 Jose Fonseca
# Copyright 2013 Atnhony Liu
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# 2013/06 Anthony Liu, ported to PyQt

'''Visualize dot graphs.'''

__author__ = "Anthony Liu"

__version__ = "0.0.1"

import os
import sys
import subprocess
import math
import colorsys
import time
import re

from PyQt4.QtCore import *
from PyQt4.QtGui import *

EOF = -1
SKIP = -2

ID = 0
STR_ID = 1
HTML_ID = 2
EDGE_OP = 3

LSQUARE = 4
RSQUARE = 5
LCURLY = 6
RCURLY = 7
COMMA = 8
COLON = 9
SEMI = 10
EQUAL = 11
PLUS = 12

STRICT = 13
GRAPH = 14
DIGRAPH = 15
NODE = 16
EDGE = 17
SUBGRAPH = 18


class Pen:

    """Store pen attributes."""
    # TODO: rewrite with QPen and QColor

    def __init__(self):
        # set default attributes
        self.color = QColor(0, 0, 0, 255)
        self.fillcolor = QColor(0, 0, 0, 255)
        self.linewidth = 1.5
        self.fontsize = 14.0
        self.fontname = "Times New Roman"
        self.style = Qt.SolidLine

    def set_fillcolor(self, tuple):
        (r, g, b, a) = tuple
        self.fillcolor = QColor(r * 255, g * 255, b * 255, a * 255)

    def set_color(self, tuple):
        (r, g, b, a) = tuple
        self.color = QColor(r * 255, g * 255, b * 255, a * 255)

    def copy(self):
        """Create a copy of this pen."""
        pen = Pen()
        pen.__dict__ = self.__dict__.copy()
        return pen

    def highlighted(self):
        pen = self.copy()
        pen.color = QColor(255, 0, 0, 255)
        pen.fillcolor = QColor(255, 200, 200, 255)
        return pen


class Shape:

    """Abstract base class for all the drawing shapes."""

    def __init__(self):
        pass

    def draw(self, scene, painer, rect, highlight=False):
        """Draw this shape with the given cairo context"""
        raise NotImplementedError

    def select_pen(self, highlight):
        if highlight:
            if not hasattr(self, 'highlight_pen'):
                self.highlight_pen = self.pen.highlighted()
            return self.highlight_pen
        else:
            return self.pen


class TextShape(Shape):

    LEFT, CENTER, RIGHT = -1, 0, 1

    def __init__(self, pen, x, y, j, w, t):
        Shape.__init__(self)
        if 0:
            print('TextShape pen', pen.fontname)
        self.pen = pen.copy()
        self.x = x
        self.y = y
        self.j = j
        self.w = w
        self.t = t

    def draw(self, scene, painter, rect, highlight=False):
        pen = self.select_pen(highlight)
        font = QFont(pen.fontname)

        if 0:
            qfd = QFontDatabase()
            for x in qfd.families():
                print(x)
            font.setStyleHint(QFont.Courier, QFont.PreferAntialias)

            # FIXME: always see strange fonts
            qfi = QFontInfo(font)

            print(qfi.family())
            print(qfi.styleHint())

        fm = QFontMetrics(font)

        w = fm.width(self.t)
        h = fm.height()

        x = self.x - w / 2
        y = self.y

        pp = QPainterPath()
        pp.moveTo(x, y)
        pp.addText(x, y, font, self.t)

        p = QPen(pen.color)
        p.setWidth(pen.linewidth)
        p.setCosmetic(True)
        painter.setPen(p)
        painter.fillPath(pp, QBrush(pen.fillcolor))

        if 0:  # DEBUG
            # show where dot thinks the text should appear
            painter.set_source_rgba(1, 0, 0, .9)
            if self.j == self.LEFT:
                x = self.x
            elif self.j == self.CENTER:
                x = self.x - 0.5 * self.w
            elif self.j == self.RIGHT:
                x = self.x - self.w
            painter.moveTo(x, self.y)
            painter.line_to(x + self.w, self.y)
            painter.stroke()


class EllipseShape(Shape):

    def __init__(self, pen, x0, y0, w, h, filled=False):
        Shape.__init__(self)

        self.drawn = False
        self.pen = pen.copy()
        self.filled = filled

        self.item = QGraphicsEllipseItem()
        self.item.setRect(QRectF(x0 - w, y0 - h, w * 2, h * 2))
        self.item.setStartAngle(180)
        self.item.setSpanAngle(360 * 16)

    def draw(self, scene, painter, rect, highlight=False):
        if self.drawn == False:
            scene.addItem(self.item)
            self.drawn = True

        p = self.select_pen(highlight)

        if (self.filled):
            self.item.setBrush(QBrush(p.fillcolor))
        else:
            pen = QPen(p.fillcolor)
            pen.setWidthF(p.linewidth)
            self.item.setPen(pen)


class PolygonShape(Shape):

    def __init__(self, pen, points, filled=False):
        Shape.__init__(self)
        self.pen = pen.copy()
        self.points = points
        self.filled = filled

    def draw(self, scene, painter, rect, highlight=False):
        path = QPainterPath()
        x0, y0 = self.points[-1]
        path.moveTo(x0, y0)
        for x, y in self.points:
            path.lineTo(x, y)
        path.closeSubpath()
        pen = self.select_pen(highlight)
        if self.filled:
            painter.fillPath(path, QBrush(pen.fillcolor))
        else:
            p = QPen(pen.color)
            p.setWidth(pen.linewidth)
            p.setCosmetic(True)
            painter.setPen(p)
            painter.drawPath(path)


class LineShape(Shape):

    def __init__(self, pen, points):
        Shape.__init__(self)
        self.pen = pen.copy()
        self.points = points

    def draw(self, scene, painter, rect, highlight=False):
        x0, y0 = self.points[0]
        painter.moveTo(x0, y0)
        for x1, y1 in self.points[1:]:
            painter.line_to(x1, y1)
        pen = self.select_pen(highlight)
        painter.set_dash(pen.style)
        painter.set_line_width(pen.linewidth)
        painter.set_source_rgba(*pen.color)
        painter.stroke()


class BezierShape(Shape):

    def __init__(self, pen, points, filled=False):
        Shape.__init__(self)
        self.pen = pen.copy()
        self.points = points
        self.filled = filled

    def draw(self, scene, painter, rect, highlight=False):
        path = QPainterPath()
        x0, y0 = self.points[0]
        path.moveTo(x0, y0)
        for i in xrange(1, len(self.points), 3):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]
            x3, y3 = self.points[i + 2]
            path.cubicTo(x1, y1, x2, y2, x3, y3)
        pen = self.select_pen(highlight)
        if self.filled:
            painter.fillPath(path, QBrush(pen.fillcolor))
        else:
            p = QPen(pen.color)
            p.setStyle(pen.style)
            p.setWidth(pen.linewidth * 1.5)
            p.setCosmetic(True)
            painter.setPen(p)
            painter.drawPath(path)


class CompoundShape(Shape):

    def __init__(self, shapes):
        Shape.__init__(self)
        self.shapes = shapes

    def draw(self, scene, painter, rect, highlight=False):
        for shape in self.shapes:
            shape.draw(scene, painter, rect, highlight=highlight)


class Url(object):

    def __init__(self, item, url, highlight=None):
        self.item = item
        self.url = url
        if highlight is None:
            highlight = set([item])
        self.highlight = highlight


class Jump(object):

    def __init__(self, item, x, y, highlight=None):
        self.item = item
        self.x = x
        self.y = y
        if highlight is None:
            highlight = set([item])
        self.highlight = highlight


class Element(CompoundShape):

    """Base class for graph nodes and edges."""

    def __init__(self, shapes):
        CompoundShape.__init__(self, shapes)

    def get_url(self, x, y):
        return None

    def get_jump(self, x, y):
        return None


class Node(Element):

    def __init__(self, x, y, w, h, shapes, url):
        Element.__init__(self, shapes)

        self.x = x
        self.y = y

        self.x1 = x - 0.5 * w
        self.y1 = y - 0.5 * h
        self.x2 = x + 0.5 * w
        self.y2 = y + 0.5 * h

        self.url = url

    def is_inside(self, x, y):
        return self.x1 <= x and x <= self.x2 and self.y1 <= y and y <= self.y2

    def get_url(self, x, y):
        if self.url is None:
            return None
        #print (x, y), (self.x1, self.y1), "-", (self.x2, self.y2)
        if self.is_inside(x, y):
            return Url(self, self.url)
        return None

    def get_jump(self, x, y):
        if self.is_inside(x, y):
            return Jump(self, self.x, self.y)
        return None


def square_distance(x1, y1, x2, y2):
    deltax = x2 - x1
    deltay = y2 - y1
    return deltax * deltax + deltay * deltay


class Edge(Element):

    def __init__(self, src, dst, points, shapes):
        Element.__init__(self, shapes)
        self.src = src
        self.dst = dst
        self.points = points

    RADIUS = 10

    def get_jump(self, x, y):
        if square_distance(x, y, *self.points[0]) <= self.RADIUS * self.RADIUS:
            return Jump(self, self.dst.x, self.dst.y, highlight=set([self, self.dst]))
        if square_distance(x, y, *self.points[-1]) <= self.RADIUS * self.RADIUS:
            return Jump(self, self.src.x, self.src.y, highlight=set([self, self.src]))
        return None


class Graph(Shape):

    def __init__(self, width=1, height=1, shapes=(), nodes=(), edges=()):
        Shape.__init__(self)

        self.width = width
        self.height = height
        self.shapes = shapes
        self.nodes = nodes
        self.edges = edges

    def get_size(self):
        return self.width, self.height

    def draw(self, scene, painter, rect, highlight_items=None):
        if highlight_items is None:
            highlight_items = ()

        # for shape in self.shapes:
        #	shape.draw(scene, painter, rect)
        for edge in self.edges:
            edge.draw(
                scene, painter, rect, highlight=(edge in highlight_items))
        for node in self.nodes:
            node.draw(
                scene, painter, rect, highlight=(node in highlight_items))

    def get_url(self, x, y):
        for node in self.nodes:
            url = node.get_url(x, y)
            if url is not None:
                return url
        return None

    def get_jump(self, x, y):
        for edge in self.edges:
            jump = edge.get_jump(x, y)
            if jump is not None:
                return jump
        for node in self.nodes:
            jump = node.get_jump(x, y)
            if jump is not None:
                return jump
        return None


class Animation(QObject):

    step = 0.03  # seconds

    def __init__(self, dot_widget):
        self.dot_widget = dot_widget
        self.timeout_id = None

    def start(self):
        self.timeout_id = self.StartTimer(int(self.step * 1000), self.tick)

    def stop(self):
        self.dot_widget.animation = NoAnimation(self.dot_widget)
        if self.timeout_id is not None:
            self.killTimer(self.timeout_id)
            self.timeout_id = None

    def tick(self):
        self.stop()


class NoAnimation(Animation):

    def start(self):
        pass

    def stop(self):
        pass


class Token:

    def __init__(self, type, text, line, col):
        self.type = type
        self.text = text
        self.line = line
        self.col = col


class ParseError(Exception):

    def __init__(self, msg=None, filename=None, line=None, col=None):
        self.msg = msg
        self.filename = filename
        self.line = line
        self.col = col

    def __str__(self):
        return ':'.join([str(part) for part in (self.filename, self.line, self.col, self.msg) if part != None])


class Parser:

    def __init__(self, lexer):
        self.lexer = lexer
        self.lookahead = self.lexer.next()

    def match(self, type):
        if self.lookahead.type != type:
            raise ParseError(
                msg='unexpected token %r' % self.lookahead.text,
                filename=self.lexer.filename,
                line=self.lookahead.line,
                col=self.lookahead.col)

    def skip(self, type):
        while self.lookahead.type != type:
            self.consume()

    def consume(self):
        token = self.lookahead
        self.lookahead = self.lexer.next()
        return token


class XDotAttrParser:

    """Parser for xdot drawing attributes.
    See also:
    - http://www.graphviz.org/doc/info/output.html#d:xdot
    """

    def __init__(self, parser, buf):
        self.parser = parser
        self.buf = self.unescape(buf)
        self.pos = 0

        self.pen = Pen()
        self.shapes = []

    def __nonzero__(self):
        return self.pos < len(self.buf)

    def unescape(self, buf):
        buf = buf.replace('\\"', '"')
        buf = buf.replace('\\n', '\n')
        return buf

    def read_code(self):
        pos = self.buf.find(" ", self.pos)
        res = self.buf[self.pos:pos]
        self.pos = pos + 1
        while self.pos < len(self.buf) and self.buf[self.pos].isspace():
            self.pos += 1
        return res

    def read_number(self):
        return int(float(self.read_code()))

    def read_float(self):
        return float(self.read_code())

    def read_point(self):
        x = self.read_number()
        y = self.read_number()
        return self.transform(x, y)

    def read_text(self):
        num = self.read_number()
        pos = self.buf.find("-", self.pos) + 1
        self.pos = pos + num
        res = self.buf[pos:self.pos]
        while self.pos < len(self.buf) and self.buf[self.pos].isspace():
            self.pos += 1
        return res

    def read_polygon(self):
        n = self.read_number()
        p = []
        for i in range(n):
            x, y = self.read_point()
            p.append((x, y))
        return p

    def read_color(self):
        # See http://www.graphviz.org/doc/info/attrs.html#k:color
        c = self.read_text()
        c1 = c[:1]
        if c1 == '#':
            hex2float = lambda h: float(int(h, 16) / 255.0)
            r = hex2float(c[1:3])
            g = hex2float(c[3:5])
            b = hex2float(c[5:7])
            try:
                a = hex2float(c[7:9])
            except (IndexError, ValueError):
                a = 1.0
            return r, g, b, a
        elif c1.isdigit() or c1 == ".":
            # "H,S,V" or "H S V" or "H, S, V" or any other variation
            h, s, v = map(float, c.replace(",", " ").split())
            r, g, b = colorsys.hsv_to_rgb(h, s, v)
            a = 1.0
            return r, g, b, a
        else:
            print 'TODO: implement text-based color parsing'
            return 0, 0, 0, 1.0

    def parse(self):
        s = self

        while s:
            op = s.read_code()
            if op == "c":
                color = s.read_color()
                if color is not None:
                    self.handle_color(color, filled=False)
            elif op == "C":
                color = s.read_color()
                if color is not None:
                    self.handle_color(color, filled=True)
            elif op == "S":
                # http://www.graphviz.org/doc/info/attrs.html#k:style
                style = s.read_text()
                if style.startswith("setlinewidth("):
                    lw = style.split("(")[1].split(")")[0]
                    lw = float(lw)
                    self.handle_linewidth(lw)
                elif style in ("solid", "dashed", "dotted"):
                    self.handle_linestyle(style)
            elif op == "F":
                size = s.read_float()
                name = s.read_text()
                self.handle_font(size, name)
            elif op == "T":
                x, y = s.read_point()
                j = s.read_number()
                w = s.read_number()
                t = s.read_text()
                self.handle_text(x, y, j, w, t)
            elif op == "E":
                x0, y0 = s.read_point()
                w = s.read_number()
                h = s.read_number()
                self.handle_ellipse(x0, y0, w, h, filled=True)
            elif op == "e":
                x0, y0 = s.read_point()
                w = s.read_number()
                h = s.read_number()
                self.handle_ellipse(x0, y0, w, h, filled=False)
            elif op == "L":
                points = self.read_polygon()
                self.handle_line(points)
            elif op == "B":
                points = self.read_polygon()
                self.handle_bezier(points, filled=False)
            elif op == "b":
                points = self.read_polygon()
                self.handle_bezier(points, filled=True)
            elif op == "P":
                points = self.read_polygon()
                self.handle_polygon(points, filled=True)
            elif op == "p":
                points = self.read_polygon()
                self.handle_polygon(points, filled=False)
            else:
                sys.stderr.write("unknown xdot opcode '%s'\n" % op)
                break

        return self.shapes

    def transform(self, x, y):
        return self.parser.transform(x, y)

    def handle_color(self, color, filled=False):
        if filled:
            self.pen.set_fillcolor(color)
        else:
            self.pen.set_color(color)

    def handle_linewidth(self, linewidth):
        self.pen.linewidth = linewidth

    def handle_linestyle(self, style):
        if style == "solid":
            self.pen.style = Qt.SolidLine
        elif style == "dashed":
            self.pen.style = Qt.DashLine
        elif style == "dotted":
            self.pen.style = Qt.DotLine

    def handle_font(self, size, name):
        self.pen.fontsize = size
        self.pen.fontname = name

    def handle_text(self, x, y, j, w, t):
        self.shapes.append(TextShape(self.pen, x, y, j, w, t))

    def handle_ellipse(self, x0, y0, w, h, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(
                EllipseShape(self.pen, x0, y0, w, h, filled=True))
        self.shapes.append(EllipseShape(self.pen, x0, y0, w, h))

    def handle_line(self, points):
        self.shapes.append(LineShape(self.pen, points))

    def handle_bezier(self, points, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(BezierShape(self.pen, points, filled=True))
        self.shapes.append(BezierShape(self.pen, points))

    def handle_polygon(self, points, filled=False):
        if filled:
            # xdot uses this to mean "draw a filled shape with an outline"
            self.shapes.append(PolygonShape(self.pen, points, filled=True))
        self.shapes.append(PolygonShape(self.pen, points))


class Lexer:

    # should be overriden by derived classes
    scanner = None
    tabsize = 8

    newline_re = re.compile(r'\r\n?|\n')

    def __init__(self, buf=None, pos=0, filename=None, fp=None):
        if fp is not None:
            try:
                fileno = fp.fileno()
                length = os.path.getsize(fp.name)
                import mmap
            except:
                # read whole file into memory
                buf = fp.read()
                pos = 0
            else:
                # map the whole file into memory
                if length:
                    # length must not be zero
                    buf = mmap.mmap(fileno, length, access=mmap.ACCESS_READ)
                    pos = os.lseek(fileno, 0, 1)
                else:
                    buf = ''
                    pos = 0

            if filename is None:
                try:
                    filename = fp.name
                except AttributeError:
                    filename = None

        self.buf = buf
        self.pos = pos
        self.line = 1
        self.col = 1
        self.filename = filename

    def next(self):
        while True:
            # save state
            pos = self.pos
            line = self.line
            col = self.col

            type, text, endpos = self.scanner.next(self.buf, pos)
            assert pos + len(text) == endpos
            self.consume(text)
            type, text = self.filter(type, text)
            self.pos = endpos

            if type == SKIP:
                continue
            elif type is None:
                msg = 'unexpected char '
                if text >= ' ' and text <= '~':
                    msg += "'%s'" % text
                else:
                    msg += "0x%X" % ord(text)
                raise ParseError(msg, self.filename, line, col)
            else:
                break
        return Token(type=type, text=text, line=line, col=col)

    def consume(self, text):
        # update line number
        pos = 0
        for mo in self.newline_re.finditer(text, pos):
            self.line += 1
            self.col = 1
            pos = mo.end()

        # update column number
        while True:
            tabpos = text.find('\t', pos)
            if tabpos == -1:
                break
            self.col += tabpos - pos
            self.col = ((self.col - 1) // self.tabsize + 1) * self.tabsize + 1
            pos = tabpos + 1
        self.col += len(text) - pos


class Scanner:

    """Stateless scanner."""

    # should be overriden by derived classes
    tokens = []
    symbols = {}
    literals = {}
    ignorecase = False

    def __init__(self):
        flags = re.DOTALL
        if self.ignorecase:
            flags |= re.IGNORECASE
        self.tokens_re = re.compile(
            '|'.join(
                ['(' + regexp + ')' for type, regexp, test_lit in self.tokens]),
            flags
        )

    def next(self, buf, pos):
        if pos >= len(buf):
            return EOF, '', pos
        mo = self.tokens_re.match(buf, pos)
        if mo:
            text = mo.group()
            type, regexp, test_lit = self.tokens[mo.lastindex - 1]
            pos = mo.end()
            if test_lit:
                type = self.literals.get(text, type)
            return type, text, pos
        else:
            c = buf[pos]
            return self.symbols.get(c, None), c, pos + 1


class DotScanner(Scanner):

    # token regular expression table
    tokens = [
        # whitespace and comments
        (SKIP,
            r'[ \t\f\r\n\v]+|'
            r'//[^\r\n]*|'
            r'/\*.*?\*/|'
            r'#[^\r\n]*',
         False),

        # Alphanumeric IDs
        (ID, r'[a-zA-Z_\x80-\xff][a-zA-Z0-9_\x80-\xff]*', True),

        # Numeric IDs
        (ID, r'-?(?:\.[0-9]+|[0-9]+(?:\.[0-9]*)?)', False),

        # String IDs
        (STR_ID, r'"[^"\\]*(?:\\.[^"\\]*)*"', False),

        # HTML IDs
        (HTML_ID, r'<[^<>]*(?:<[^<>]*>[^<>]*)*>', False),

        # Edge operators
        (EDGE_OP, r'-[>-]', False),
    ]

    # symbol table
    symbols = {
        '[': LSQUARE,
        ']': RSQUARE,
        '{': LCURLY,
        '}': RCURLY,
        ',': COMMA,
        ':': COLON,
        ';': SEMI,
        '=': EQUAL,
        '+': PLUS,
    }

    # literal table
    literals = {
        'strict': STRICT,
        'graph': GRAPH,
        'digraph': DIGRAPH,
        'node': NODE,
        'edge': EDGE,
        'subgraph': SUBGRAPH,
    }

    ignorecase = True


class DotLexer(Lexer):

    scanner = DotScanner()

    def filter(self, type, text):
        # TODO: handle charset
        if type == STR_ID:
            text = text[1:-1]

            # line continuations
            text = text.replace('\\\r\n', '')
            text = text.replace('\\\r', '')
            text = text.replace('\\\n', '')

            text = text.replace('\\r', '\r')
            text = text.replace('\\n', '\n')
            text = text.replace('\\t', '\t')
            text = text.replace('\\', '')

            type = ID

        elif type == HTML_ID:
            text = text[1:-1]
            type = ID

        return type, text


class DotParser(Parser):

    def __init__(self, lexer):
        Parser.__init__(self, lexer)
        self.graph_attrs = {}
        self.node_attrs = {}
        self.edge_attrs = {}

    def parse(self):
        self.parse_graph()
        self.match(EOF)

    def parse_graph(self):
        if self.lookahead.type == STRICT:
            self.consume()
        self.skip(LCURLY)
        self.consume()
        while self.lookahead.type != RCURLY:
            self.parse_stmt()
        self.consume()

    def parse_subgraph(self):
        id = None
        if self.lookahead.type == SUBGRAPH:
            self.consume()
            if self.lookahead.type == ID:
                id = self.lookahead.text
                self.consume()
        if self.lookahead.type == LCURLY:
            self.consume()
            while self.lookahead.type != RCURLY:
                self.parse_stmt()
            self.consume()
        return id

    def parse_stmt(self):
        if self.lookahead.type == GRAPH:
            self.consume()
            attrs = self.parse_attrs()
            self.graph_attrs.update(attrs)
            self.handle_graph(attrs)
        elif self.lookahead.type == NODE:
            self.consume()
            self.node_attrs.update(self.parse_attrs())
        elif self.lookahead.type == EDGE:
            self.consume()
            self.edge_attrs.update(self.parse_attrs())
        elif self.lookahead.type in (SUBGRAPH, LCURLY):
            self.parse_subgraph()
        else:
            id = self.parse_node_id()
            if self.lookahead.type == EDGE_OP:
                self.consume()
                node_ids = [id, self.parse_node_id()]
                while self.lookahead.type == EDGE_OP:
                    node_ids.append(self.parse_node_id())
                attrs = self.parse_attrs()
                for i in range(0, len(node_ids) - 1):
                    self.handle_edge(node_ids[i], node_ids[i + 1], attrs)
            elif self.lookahead.type == EQUAL:
                self.consume()
                self.parse_id()
            else:
                attrs = self.parse_attrs()
                self.handle_node(id, attrs)
        if self.lookahead.type == SEMI:
            self.consume()

    def parse_attrs(self):
        attrs = {}
        while self.lookahead.type == LSQUARE:
            self.consume()
            while self.lookahead.type != RSQUARE:
                name, value = self.parse_attr()
                attrs[name] = value
                if self.lookahead.type == COMMA:
                    self.consume()
            self.consume()
        return attrs

    def parse_attr(self):
        name = self.parse_id()
        if self.lookahead.type == EQUAL:
            self.consume()
            value = self.parse_id()
        else:
            value = 'true'
        return name, value

    def parse_node_id(self):
        node_id = self.parse_id()
        if self.lookahead.type == COLON:
            self.consume()
            port = self.parse_id()
            if self.lookahead.type == COLON:
                self.consume()
                compass_pt = self.parse_id()
            else:
                compass_pt = None
        else:
            port = None
            compass_pt = None
        # XXX: we don't really care about port and compass point values when
        # parsing xdot
        return node_id

    def parse_id(self):
        self.match(ID)
        id = self.lookahead.text
        self.consume()
        return id

    def handle_graph(self, attrs):
        pass

    def handle_node(self, id, attrs):
        pass

    def handle_edge(self, src_id, dst_id, attrs):
        pass


class XDotParser(DotParser):

    def __init__(self, xdotcode):
        lexer = DotLexer(buf=xdotcode)
        DotParser.__init__(self, lexer)

        self.nodes = []
        self.edges = []
        self.shapes = []
        self.node_by_name = {}
        self.top_graph = True

    def handle_graph(self, attrs):
        if self.top_graph:
            try:
                bb = attrs['bb']
            except KeyError:
                return

            if not bb:
                return

            xmin, ymin, xmax, ymax = map(float, bb.split(","))

            self.xoffset = -xmin
            self.yoffset = -ymax
            self.xscale = 1.0
            self.yscale = -1.0
            # FIXME: scale from points to pixels

            self.width = xmax - xmin
            self.height = ymax - ymin

            self.top_graph = False

        for attr in ("_draw_", "_ldraw_", "_hdraw_", "_tdraw_", "_hldraw_", "_tldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                self.shapes.extend(parser.parse())

    def handle_node(self, id, attrs):
        try:
            pos = attrs['pos']
        except KeyError:
            return

        x, y = self.parse_node_pos(pos)
        w = float(attrs['width']) * 72
        h = float(attrs['height']) * 72
        shapes = []
        for attr in ("_draw_", "_ldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                shapes.extend(parser.parse())
        url = attrs.get('URL', None)
        node = Node(x, y, w, h, shapes, url)
        self.node_by_name[id] = node
        if shapes:
            self.nodes.append(node)

    def handle_edge(self, src_id, dst_id, attrs):
        try:
            pos = attrs['pos']
        except KeyError:
            return

        points = self.parse_edge_pos(pos)
        shapes = []
        for attr in ("_draw_", "_ldraw_", "_hdraw_", "_tdraw_", "_hldraw_", "_tldraw_"):
            if attr in attrs:
                parser = XDotAttrParser(self, attrs[attr])
                shapes.extend(parser.parse())
        if shapes:
            src = self.node_by_name[src_id]
            dst = self.node_by_name[dst_id]
            self.edges.append(Edge(src, dst, points, shapes))

    def parse(self):
        DotParser.parse(self)

        return Graph(self.width, self.height, self.shapes, self.nodes, self.edges)

    def parse_node_pos(self, pos):
        x, y = pos.split(",")
        return self.transform(float(x), float(y))

    def parse_edge_pos(self, pos):
        points = []
        for entry in pos.split(' '):
            fields = entry.split(',')
            try:
                x, y = fields
            except ValueError:
                # TODO: handle start/end points
                continue
            else:
                points.append(self.transform(float(x), float(y)))
        return points

    def transform(self, x, y):
        # XXX: this is not the right place for this code
        x = (x + self.xoffset) * self.xscale
        y = (y + self.yoffset) * self.yscale
        return x, y


class QDotWidget(QGraphicsView):

    """PyQT widget that draws dot graphs."""
    graph = None

    def __init__(self, parent=None):
        QGraphicsView.__init__(self)
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(QRectF(0, 0, 200, 300))
        self.setScene(self._scene)
        #self._scene.addText("Hello, world!");

        self.setDragMode(self.ScrollHandDrag)
        self.setTransformationAnchor(self.AnchorUnderMouse)

        self.x, self.y = 0.0, 0.0
        #self.zoom_ratio = 1.0
        self.zoom_to_fit_on_resize = False
        self.animation = NoAnimation(self)
        self.presstime = None
        self.highlight = None

    def set_dotcode(self, dotcode, filename='<stdin>'):
        if isinstance(dotcode, unicode):
            dotcode = dotcode.encode('utf8')
        p = subprocess.Popen(
            [self.filter, '-Txdot'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            universal_newlines=True
        )
        xdotcode, error = p.communicate(dotcode)
        if p.returncode != 0:
            mbox = QMessageBox()
            mbox.setWindowTitle('QDot Viewer')
            mbox.setText('Error: ' + error)
            mbox.exec_()
            return False
        try:
            self.set_xdotcode(xdotcode)
        except ParseError, ex:
            mbox = QMessageBox(self)
            mbox.setWindowTitle('QDot Viewer')
            mbox.setText('Error: ' + str(ex))
            mbox.exec_()
            return False
        else:
            self.openfilename = filename
            return True

    def set_xdotcode(self, xdotcode):
        parser = XDotParser(xdotcode)
        self.graph = parser.parse()
        (w, h) = self.graph.get_size()
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self.setScene(self._scene)

        self.resize(w, h)

        #self.zoom_image(self.zoom_ratio, center=True)

    def zoom_image(self, zoom_ratio, center=False, pos=None):
        self.scale(zoom_ratio, zoom_ratio)

    def zoom_to_area(self, x1, y1, x2, y2):
        self.fitInView(QRectF(x1, y1, x2, y2), Qt.KeepAspectRatio)

    def zoom_to_fit(self):
        rectf = self._scene.sceneRect()
        self.fitInView(rectf, Qt.KeepAspectRatio)

    def zoom_cancel(self):
        self.resetTransform()
        #self.zoom_ratio = 1.0

    def set_filter(self, filter):
        self.filter = filter

    def drawForeground(self, painter, rect):
        if self.graph:
            self.graph.draw(self._scene, painter, rect)

    def wheelEvent(self, event):
        if event.delta() > 0:
            self.zoom_image(1.0 + 1.0 / 3)
        else:
            self.zoom_image(3.0 / 4)


class QDotWindow(QWidget):

    def __init__(self, parent=None):
        super(QDotWindow, self).__init__(parent)
        self.createLayout()

    def createLayout(self):

        h1 = QHBoxLayout()

        #
        # Todo: add save, load button
        #
        if h1 != None:
            toolbar = QToolBar("ToolBar")
            if toolbar != None:
                zoomInAct = QAction(
                    QIcon.fromTheme('zoom-in'), 'Zoom In', self)
                zoomInAct.triggered.connect(self.onZoomIn)
                toolbar.addAction(zoomInAct)
                zoomOutAct = QAction(
                    QIcon.fromTheme('zoom-out'), 'Zoom Out', self)
                zoomOutAct.triggered.connect(self.onZoomOut)
                toolbar.addAction(zoomOutAct)
                zoomFitAct = QAction(
                    QIcon.fromTheme('zoom-fit-best'), 'Zoom Fit', self)
                zoomFitAct.triggered.connect(self.onZoomFit)
                toolbar.addAction(zoomFitAct)
                zoom100Act = QAction(
                    QIcon.fromTheme('zoom-original'), 'Zoom 100%', self)
                zoom100Act.triggered.connect(self.onZoom100)
                toolbar.addAction(zoom100Act)
            h1.addWidget(toolbar)

        self.dotwidget = QDotWidget()
        h2 = QHBoxLayout()
        h2.addWidget(self.dotwidget)

        layout = QVBoxLayout()
        layout.addLayout(h1)
        layout.addLayout(h2)

        self.setLayout(layout)

    def onZoomIn(self):
        self.dotwidget.zoom_image(1.0 + 1.0 / 3)

    def onZoomOut(self):
        self.dotwidget.zoom_image(3.0 / 4)

    def onZoomFit(self):
        self.dotwidget.zoom_to_fit()

    def onZoom100(self):
        self.dotwidget.zoom_cancel()

    def set_dotcode(self, dotcode, filename='<stdin>'):
        if self.dotwidget.set_dotcode(dotcode, filename):
            self.setWindowTitle(os.path.basename(filename) + ' - Dot Viewer')
            self.dotwidget.zoom_to_fit()

    def set_xdotcode(self, xdotcode, filename='<stdin>'):
        if self.dotwidget.set_xdotcode(xdotcode):
            self.setWindowTitle(os.path.basename(filename) + ' - Dot Viewer')
            self.dotwidget.zoom_to_fit()

    def open_file(self, filename):
        try:
            fp = file(filename, 'rt')
            self.set_dotcode(fp.read(), filename)
            fp.close()
        except IOError, ex:
            mbox = QMessageBox(self)
            mbox.setText('File not found or can not open: ' + filename)
            mbox.exec_()
            sys.exit()

    def set_filter(self, filter):
        self.dotwidget.set_filter(filter)


def debug_trace():
    '''Set a tracepoint in the Python debugger that works with Qt'''
    from PyQt4.QtCore import pyqtRemoveInputHook
    from pdb import set_trace
    pyqtRemoveInputHook()
    set_trace()


def main():
    import optparse

    parser = optparse.OptionParser(
        usage='\n\t%prog [file]',
        version='%%prog %s' % __version__)
    parser.add_option(
        '-f', '--filter',
        type='choice', choices=('dot', 'neato', 'twopi', 'circo', 'fdp'),
        dest='filter', default='dot',
        help='graphviz filter: dot, neato, twopi, circo, or fdp [default: %default]')

    (options, args) = parser.parse_args(sys.argv[1:])
    if len(args) > 1:
        parser.error('incorrect number of arguments')

    app = QApplication(sys.argv)
    win = QDotWindow()
    win.show()

    win.set_filter(options.filter)
    if len(args) >= 1:
        if args[0] == '-':
            win.set_dotcode(sys.stdin.read())
        else:
            win.open_file(args[0])

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
