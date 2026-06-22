import socket
import ssl
import os
import time
import gzip
import tkinter
import tkinter.font


WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

SOCKETS = {}
CACHE = {}
FONTS = {}

DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "test.html")
DEFAULT_URL = "file:///" + DEFAULT_FILE.replace("\\", "/")



"""     **********        STANDALONE CLASSES       **********       """

class Text:
    def __init__(self, text):
        self.text = text

class Tag:
    def __init__(self, tag):
        self.tag = tag

"""     **********        STANDALONE METHODS       **********       """

def lex(body):
    out = []
    buffer = ""
    in_tag = False
    i = 0
    while i < len(body):
        if body[i:i+4] == "&lt;": 
            buffer += "<"
            i += 4
            continue
        elif body[i:i+4] == "&gt;":
            buffer += ">"
            i += 4
            continue
        elif body[i:i+5] == "&shy;":
            buffer +="\u00ad"
            i += 5
            continue
        elif body[i] == "<":
            in_tag = True
            if buffer:
                out.append(Text(buffer))
                buffer = ""
        elif body[i] == ">":
            in_tag = False
            out.append(Tag(buffer))
            buffer = ""
        else:
            buffer += body[i]
        i += 1

    if not in_tag and buffer:
        out.append(Text(buffer))

    for item in out:
        print(type(item), getattr(item, "text", None), getattr(item, "tag", None))

    return out


def get_font(size, weight, style, family="Times"):
    key = (size, weight, style, family)

    if key not in FONTS:
        font = tkinter.font.Font(
            family=family,
            size=size,
            weight=weight,
            slant =style
        )
        label = tkinter.Label(font=font)
        FONTS[key] = (font, label)
    
    return FONTS[key][0]

def longest_fit(parts, cursor_x, font):
    current = ""
    last_fit = ""
    fit_count = 0

    for part in parts[:-1]:
        candidate = current + part + "-"

        if cursor_x + font.measure(candidate) > WIDTH - HSTEP:
            break
    
        current += part
        last_fit = current
        fit_count += 1
    
    return last_fit, fit_count




"""     **********        LAYOUT       **********       """


class Layout:
    def __init__(self, tokens, rtl):
        self.display_list = []
        self.cursor_x = HSTEP
        self.cursor_y = VSTEP
        self.weight = "normal"
        self.style = "roman"
        self.size = 12
        self.superscript = False
        self.rtl = rtl
        # font = tkinter.font.Font()

        # if rtl:
        #     display_list = []
        #     cursor_x, cursor_y = WIDTH, VSTEP
        #     for tok in tokens:
        #         if isinstance(tok, Text):
        #             for word in tok.text.split():
        #                 width_of_word = font.measure(word)
                        
        #                 if cursor_x < HSTEP:
        #                     cursor_y += font.metrics("linespace") * 1.25
        #                     cursor_x = WIDTH - HSTEP

        #                 display_list.append((cursor_x, cursor_y, word, font))
        #                 cursor_x -= width_of_word + font.measure(" ")
        # WILL BE IMPLEMENTED LATER !!!!!!!!!!
        
        self.line = []
        self.centered = False
        self.abbr = False
        self.preformat = False
        
        for tok in tokens:
            self.token(tok)

        self.flush()

    def token(self, tok):
        if isinstance(tok, Text):
            if self.preformat:
                for c in tok.text:
                    self.character(c)
            else:
                for word in tok.text.split():
                    self.word(word)
        elif tok.tag == "i":
            self.style = "italic"
        elif tok.tag == "/i":
            self.style = "roman"
        elif tok.tag == "b":
            self.weight = "bold"
        elif tok.tag == "/b":
            self.weight = "normal"
        elif tok.tag == "small":
            self.size -= 2
        elif tok.tag == "/small":
            self.size += 2
        elif tok.tag == "big":
            self.size += 4
        elif tok.tag == "/big":
            self.size -= 4
        elif tok.tag == "br":
            self.flush()
        elif tok.tag == "/p":
            self.flush()
            self.cursor_y += VSTEP
        elif tok.tag.startswith("h1") and 'class="title"' in tok.tag:
            self.centered = True
        elif tok.tag == "/h1":
            self.flush()
            self.centered = False
        elif tok.tag == "sup":
            self.superscript = True
        elif tok.tag == "/sup":
            self.superscript = False
        elif tok.tag == "abbr":
            self.abbr = True
        elif tok.tag == "/abbr":
            self.abbr = False
        elif tok.tag == "pre":
            self.flush()
            self.preformat = True
        elif tok.tag == "/pre":
            self.flush()
            self.preformat = False

        

    def character(self, c):
        font = get_font(self.size, self.weight, self.style, family="Courier New")

        if c == "\n":
            self.flush()
            return
        
        self.line.append((self.cursor_x, c, font, self.superscript))
        self.cursor_x += font.measure(c)

    def word(self, word):
        if self.abbr:
            for c in word:
                if c.islower():
                    char = c.upper()
                    font = get_font(self.size - 2, "bold", self.style)
                else:
                    char = c
                    font = get_font(self.size, self.weight, self.style)

                width = font.measure(char)

                if self.cursor_x + width > WIDTH - HSTEP:
                    self.flush()
                
                self.line.append((self.cursor_x, char, font, self.superscript))
                self.cursor_x += width
            self.cursor_x += get_font(self.size, self.weight, self.style).measure(" ")
            return                    
        else:
            size = self.size

            if self.superscript:
                size = self.size // 2
            

            font = get_font(size, self.weight, self.style)
            
            visible_word = word.replace("\u00ad", "")
            width_of_word = font.measure(visible_word)

            
            if self.cursor_x + width_of_word > WIDTH - HSTEP:  
                if "\u00ad" not in word:
                    self.flush()
                else:
                    remaining = word
                    while "\u00ad" in remaining:
                        parts = remaining.split("\u00ad")
                        fit, idx = longest_fit(parts, self.cursor_x, font)

                        if fit == "":
                            self.flush()
                            fit, idx = longest_fit(parts, self.cursor_x, font)
                            
                        

                        self.line.append((self.cursor_x, fit + "-", font, self.superscript))
                        self.flush()


                        remaining = "\u00ad".join(parts[idx:])
                        self.word(remaining)
                        return

            self.line.append((self.cursor_x, visible_word, font, self.superscript))
            self.cursor_x += width_of_word +font.measure(" ")

    def flush(self):
        
        if not self.line: return

        offset = 0

        if self.centered:
            last_x, last_word, last_font, superscript = self.line[-1]
            first_x, _, _, _ = self.line[0]

            line_width = last_x + last_font.measure(last_word) - first_x

            offset = (WIDTH - line_width) / 2 - first_x

        
        metrics = [font.metrics() for x, word, font, sup in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])

        baseline = self.cursor_y + 1.25 * max_ascent

        for x, word, font, sup in self.line:
            if sup:
                y = baseline - max_ascent
            else:
                y = baseline - font.metrics("ascent")
            x = x + offset
            self.display_list.append((x, y, word, font))

        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent

        self.cursor_x = HSTEP
        self.line = []

    





"""     **********        URL       **********       """
class URL:
    def __init__(self, url):
        self.view_source = False

        try:
            if url.startswith("view-source:"):
                self.view_source = True
                url = url[len("view-source:"):]
            
            if url.startswith("data:"):
                self.scheme, url = url.split(":", 1)
            else:
                self.scheme, url = url.split("://", 1)

            assert self.scheme in ["http", "https", "file", "data"]

            if self.scheme == "data":
                self.media, self.body = url.split(",", 1)
                return
            
            elif self.scheme == "file":
                self.path = url
                if self.path.startswith("/") and self.path[2] == ":":
                    self.path = self.path[1:]
                return
            
            else:
                if "/" not in url:
                    url = url + "/"
                self.host, url = url.split("/", 1)
                self.path = "/" + url

                if self.scheme == "http":
                    self.port = 80
                elif self.scheme == "https":
                    self.port = 443
                
                if ":" in self.host:
                    self.host, port = self.host.split(":", 1)
                    self.port = int(port)
        except:
            self.scheme = "about"
            self.path = "blank"
            
    
    def request(self):        
        
        if self.scheme == "about":
            return "200", {}, ""

        if self.scheme == "data":
            content = self.body
            return "200", {}, content

        elif self.scheme == "file":
            with open(self.path) as f:
                content = f.read()
            return "200", {}, content
        
        else:
            socket_key = (self.scheme, self.host, self.port)
            cache_key = (self.scheme, self.host, self.port, self.path)

            if cache_key in CACHE:
                cached_time, status, headers, body = CACHE[cache_key]
                age = time.time() - cached_time

                max_age = None
                cache_control = headers.get("cache-control")
                # to fetch "max_age"
                parts = cache_control.split(",")
                for part in parts:
                    part = part.strip()
                    if part.startswith("max-age="):
                        max_age = int(part.split("=", 1)[1])

                # age control
                if max_age is not None and age < max_age:
                    print("-------------------....LOAD FROM CACHE....-------------------")
                    return status, headers, body
                else:
                    print("------------------ MAX AGE ===", max_age)
                    print("------------------ AGE ===", age) 
                    del CACHE[cache_key]
                


            # Socket Manipulation
            if socket_key in SOCKETS:
                s, response = SOCKETS[socket_key]
                print("-------------------....REUSE SOCKET....-------------------")
            else:
                s = socket.socket(
                    family=socket.AF_INET,
                    type=socket.SOCK_STREAM,
                    proto=socket.IPPROTO_TCP,
                )
                s.connect((self.host, self.port))
                if self.scheme == "https":
                    ctx = ssl.create_default_context()
                    s = ctx.wrap_socket(s, server_hostname=self.host)
                # add new socket and response to reuse them in future
                response = s.makefile("rb")
                SOCKETS[socket_key] = s, response
                print("-------------------...OPEN NEW SOCKET...-------------------")

            # Request Manipulation
            headers = {
                "Host": self.host,
                "Connection": "keep-alive",
                "User-Agent": "KerimBrowser",
                "Accept-Encoding": "gzip"
            }
            # Start with the Method Path Version
            request = "GET {} HTTP/1.1\r\n".format(self.path)
            for header, value in headers.items():
                request += "{}: {}\r\n".format(header, value)
            request += "\r\n"
            # Send Request
            s.send(request.encode("utf8"))

            # Response Manipulation
            statusline = response.readline().decode("utf-8")
            version, status, explanation = statusline.split(" ", 2)


            response_headers = {}
            while True:
                line = response.readline()
                if line == b"\r\n" :
                    break
                line = line.decode("utf-8")
                header, value = line.split(":", 1)
                response_headers[header.casefold()] = value.strip()

            print(response_headers) # just to check response headers what they include
            if "transfer-encoding" in response_headers:
                assert response_headers["transfer-encoding"] == "chunked"
            if "content-encoding" in response_headers:
                assert response_headers["content-encoding"] == "gzip"

            if response_headers.get("transfer-encoding") == "chunked":
                content = b""

                while True:
                    size_line = response.readline()
                    size = int(size_line, 16)

                    if size == 0:
                        response.readline()
                        break

                    content += response.read(size)
                    response.readline()
            else:
                content_len = int(response_headers["content-length"])
                content = response.read(content_len)

            if response_headers.get("content-encoding") == "gzip":
                content = gzip.decompress(content)
            
            content = content.decode("utf-8")

            cache_control = response_headers.get("cache-control")
            
            if status == "200":
                if cache_control and "no-store" in cache_control:
                    pass
                elif cache_control and "max-age=" in cache_control:
                    print("SAVED TO CACHE", cache_key, cache_control)   
                    CACHE[cache_key] = time.time(), status, response_headers, content
        
        return status, response_headers, content


"""     **********        BROWSER       **********       """
class Browser:
    def __init__(self, rtl=False):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)

        self.tokens = None
        self.font = None
        self.display_list = None
        self.rtl = rtl

        self.emoji = tkinter.PhotoImage(file="emoji_grinning_16.png")

        self.scroll = 0
        self.window.bind("<Down>", self.scrollDown)
        self.window.bind("<Up>",self.scrollUp)
        self.window.bind("<MouseWheel>", self.mouseWheel)
        self.window.bind("<Configure>", self.resize)

    def draw(self):
        self.canvas.delete("all")
        if not self.display_list:
            return
        for x,y,c,font in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.font = font
            
            if c == "😀":
                self.canvas.create_image(x, y - self.scroll, image=self.emoji)
            else:
                self.canvas.create_text(x, y - self.scroll, text=c, font=self.font, anchor="nw")
        
        last_y = max(y for x, y, c, font in self.display_list)

        document_height = last_y + VSTEP
        viewport_height = HEIGHT

        if document_height > viewport_height:
            thumb_height = HEIGHT * (viewport_height / document_height)
            thumb_y = HEIGHT * (self.scroll / document_height)

            x1 = WIDTH - HSTEP
            x2 = WIDTH
            y1 = thumb_y
            y2 = thumb_y + thumb_height

            self.canvas.create_rectangle(x1,y1,x2,y2, fill="blue")




    def resize(self, e):
        global WIDTH, HEIGHT
        WIDTH = e.width
        HEIGHT = e.height

        if hasattr(self, "tokens"):
            self.display_list = Layout(self.tokens, self.rtl).display_list
            self.draw()

    def scrollDown(self, e):
        if not self.display_list:
            return
        last_y = max(y for x, y, c, font in self.display_list)
        max_scroll = max(0, last_y + VSTEP - HEIGHT)

        self.scroll += SCROLL_STEP

        if self.scroll > max_scroll:
            self.scroll = max_scroll
        self.draw()

    def scrollUp(self, e):
        self.scroll -= SCROLL_STEP
        if self.scroll < 0:
            self.scroll = 0
        self.draw()
    
    def mouseWheel(self, e):
        if e.delta < 0:
            self.scrollDown(e)
        else:
            self.scrollUp(e)

    def load(self, url, redirects=0):

        status, headers, body = url.request()

        if status.startswith("3"):
            if redirects >= 10:
                print("TOO MANY REDIRECTS....")
                return
        
            print("Redirecting to: {}".format(headers["location"]))
            location = headers["location"]

            if location.startswith("/"):
                location = url.scheme + "://" + url.host + location

            self.load(URL(location), redirects + 1)
            return
            
        if url.view_source:
            self.tokens = body
        else:
            self.tokens = lex(body=body)
        
        self.display_list = Layout(self.tokens, self.rtl).display_list
        self.draw()


if __name__ == "__main__":
    import sys

    rtl = False # for the cases that alternate text direction may need
    if "--rtl" in sys.argv:
        rtl = True
        sys.argv.remove("--rtl")

    if len(sys.argv) > 1:
        Browser(rtl).load(URL(sys.argv[1]))
        tkinter.mainloop()
    else:
        Browser(rtl).load(URL(DEFAULT_URL))
        tkinter.mainloop()
        # load(URL("http://browser.engineering/http.html"))
        # load(URL("http://browser.engineering/http.html/http.html"))