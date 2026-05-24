import socket
import ssl
import os
import time
import gzip
import tkinter

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100

SOCKETS = {}
CACHE = {}

DEFAULT_FILE = os.path.join(os.path.dirname(__file__), "test.html")
DEFAULT_URL = "file:///" + DEFAULT_FILE.replace("\\", "/")



"""     **********        STANDALONE METHODS       **********       """

def lex(body):
    text = ""
    in_tag = False
    i = 0
    while i < len(body):
        if body[i:i+4] == "&lt;": 
            text += "<"
            i += 4
            continue
        elif body[i:i+4] == "&gt;":
            text += ">"
            i += 4
            continue
        elif body[i] == "<":
            in_tag = True
        elif body[i] == ">":
            in_tag = False
        elif not in_tag:
            text += body[i]
        i += 1

    return text

def layout(text):
    
    display_list = []
    cursor_x, cursor_y = HSTEP, VSTEP
    for c in text:
        if c == "\n": # checking for new line to start the next words in a new paragraph
            cursor_y += VSTEP
            cursor_x = HSTEP
            continue

        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP
        
        if cursor_x > WIDTH - HSTEP:
            cursor_y += VSTEP * 2
            cursor_x = HSTEP

    return display_list


"""     **********        URL       **********       """
class URL:
    def __init__(self, url):
        self.view_source = False

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
    
    def request(self):        
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
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window,
            width=WIDTH,
            height=HEIGHT
        )
        self.canvas.pack(fill=tkinter.BOTH, expand=True)

        self.text = None

        self.scroll = 0
        self.window.bind("<Down>", self.scrollDown)
        self.window.bind("<Up>",self.scrollUp)
        self.window.bind("<MouseWheel>", self.mouseWheel)
        self.window.bind("<Configure>", self.resize)

    def draw(self):
        self.canvas.delete("all")
        for x,y,c in self.display_list:
            if y > self.scroll + HEIGHT: continue
            if y + VSTEP < self.scroll: continue
            self.canvas.create_text(x, y - self.scroll, text=c)

    def resize(self, e):
        global WIDTH, HEIGHT
        WIDTH = e.width
        HEIGHT = e.height

        if hasattr(self, "text"):
            self.display_list = layout(self.text)
            self.draw()

    def scrollDown(self, e):
        self.scroll += SCROLL_STEP
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
            print(body)
        else:
            self.text = lex(body=body)
        
        self.display_list = layout(self.text)
        self.draw()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        Browser().load(URL(sys.argv[1]))
        tkinter.mainloop()
    else:
        Browser().load(URL(DEFAULT_URL))
        tkinter.mainloop()
        # load(URL("http://browser.engineering/http.html"))
        # load(URL("http://browser.engineering/http.html/http.html"))