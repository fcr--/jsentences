import urllib.parse
import http.server

class BasicWeb(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        # self.parsed_path.path does not include query params ie: /foo/bar
        self.parsed_path: urllib.parse.ParseResult = urllib.parse.urlparse(self.path)
        self.parsed_query: Dict[str, List[str]] = urllib.parse.parse_qs(self.parsed_path.query)

        m = getattr(self, 'tool_' + self.parsed_path.path.split('/')[1], None)
        if m is not None:
            code, res = m()
        else:
            code, res = 404, 'Select one of the tools above!'

        self.send_response(code)
        self.send_header('Content-type', 'text/html; charset=UTF-8')
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(
            b'<html><body bgcolor="Black" text="Lime" link="Lime" vlink="Lime"><pre>'
            b'Tools: ' + ' '.join(
                '[<a href="{x}">{x}</a>]'.format(x=x)
                for method_name in dir(self) if method_name.startswith('tool_')
                for x in [method_name[5:]]
            ).encode() +
            b'<hr>' + res.encode()
        )
        self.wfile.write(b'</pre></body></html>')

    @classmethod
    def start(cls, port):
        print('Connect to: http://localhost:{}/'.format(port))

        cls.httpd = http.server.HTTPServer(('localhost', port), cls)
        cls.httpd.serve_forever()
