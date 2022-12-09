"""

Litecord
Copyright (C) 2018-2021  Luna Mendes and Litecord Contributors

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, version 3 of the License.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

from quart import Blueprint, current_app as app, render_template_string, send_file
from pathlib import Path

bp = Blueprint("static", __name__)


@bp.route("/<path:path>")
async def static_pages(path):
    """Map requests from / to /static."""
    if ".." in path:
        return "no", 404

    static_path = Path.cwd() / Path("static") / path
    if static_path.exists():
        return await send_file(static_path)
    else:
        return "not found", 404


@bp.route("/")
@bp.route("/api")
async def index_handler():
    """Handler for the index page."""
    index_path = Path.cwd() / Path("static") / "index.html"
    return await render_template_string(
        index_path.read_text(), inst_name=app.config["NAME"]
    )
