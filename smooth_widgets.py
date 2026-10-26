"""Contours supersamplés pour CustomTkinter 5.2.2.

L'adaptateur conserve les widgets, leurs événements et la navigation clavier.
Seules leurs primitives graphiques sont remplacées par des calques RGBA PIL
calculés en 4x puis réduits. Aucun glyphe de police ne sert à dessiner les angles.
"""
from functools import lru_cache
import math
from PIL import Image, ImageDraw, ImageTk


@lru_cache(maxsize=256)
def raster(width, height, shape, bounds, radius, color, clip=None):
    scale = 4
    image = Image.new("RGBA", (width*scale, height*scale))
    draw = ImageDraw.Draw(image)
    if shape == "round":
        box = tuple(value*scale for value in bounds)
        if box[2] > box[0] and box[3] > box[1]:
            draw.rounded_rectangle(box, radius=max(0, radius*scale), fill=color)
    else:
        points = [(bounds[i]*scale, bounds[i+1]*scale) for i in range(0, len(bounds), 2)]
        draw.line(points, fill=color, width=max(1, round(radius*scale)), joint="curve")
        for x, y in (points[0], points[-1]):
            r = radius*scale/2
            draw.ellipse((x-r, y-r, x+r, y+r), fill=color)
    if clip:
        left, top, right, bottom = [round(value*scale) for value in clip]
        if left:
            image.paste((0, 0, 0, 0), (0, 0, left, height*scale))
        if top:
            image.paste((0, 0, 0, 0), (0, 0, width*scale, top))
        if right < width*scale:
            image.paste((0, 0, 0, 0), (right, 0, width*scale, height*scale))
        if bottom < height*scale:
            image.paste((0, 0, 0, 0), (0, bottom, width*scale, height*scale))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _paint(canvas, layer):
    params = layer["params"]
    color = layer.get("color", "#000000")
    if not color.startswith("#"):
        color = "#" + "".join(f"{channel//257:02x}" for channel in canvas.winfo_rgb(color))
    layer["photo"] = ImageTk.PhotoImage(raster(*params[:5], color, params[5]))
    canvas.itemconfigure(layer["id"], image=layer["photo"])


def _layer(engine, tag, width, height, bounds, radius, shape="round", clip=None):
    canvas = engine._canvas
    width, height = max(1, int(math.ceil(width))), max(1, int(math.ceil(height)))
    params = (width, height, shape, tuple(bounds), radius, tuple(clip) if clip else None)
    if not hasattr(canvas, "_reliane_layers"):
        canvas._reliane_layers = {}
    layer = canvas._reliane_layers.get(tag)
    created = not layer or not canvas.find_withtag(tag)
    if created:
        layer = {"id": canvas.create_image(0, 0, anchor="nw", tags=(tag, "reliane_raster")), "params": params}
        canvas._reliane_layers[tag] = layer
    changed = layer["params"] != params
    layer["params"] = params
    if created or changed:
        _paint(canvas, layer)
    return created or changed


def rounded(engine, width, height, radius, border, overwrite_preferred_drawing_method=None):
    radius = min(radius, width/2, height/2)
    changed = _layer(engine, "border_parts", width, height, (0, 0, width-0.25, height-0.25), radius)
    engine._canvas.itemconfigure(engine._canvas._reliane_layers["border_parts"]["id"], state="normal" if border else "hidden")
    changed |= _layer(engine, "inner_parts", width, height,
                      (border, border, width-border-0.25, height-border-0.25), max(0, radius-border))
    engine._canvas.tag_lower("border_parts")
    return changed


def split(engine, width, height, radius, border, split_pos):
    radius = min(radius, width/2, height/2)
    bounds = (0, 0, width-0.25, height-0.25)
    changed = _layer(engine, "inner_parts_left", width, height, bounds, radius, clip=(0, 0, split_pos, height))
    changed |= _layer(engine, "inner_parts_right", width, height, bounds, radius, clip=(split_pos, 0, width, height))
    if engine._canvas.find_withtag("dropdown_arrow"):
        engine._canvas.tag_raise("dropdown_arrow")
    return changed


def arrow(engine, x, y, size):
    width, height = max(1, int(math.ceil(x*2))), max(1, int(math.ceil(y*2)))
    span = max(3, size*0.38)
    result = _layer(engine, "dropdown_arrow", width, height,
                    (x-span, y-span*0.38, x, y+span*0.5, x+span, y-span*0.38), 1.5, "line")
    engine._canvas.tag_raise("dropdown_arrow")
    return result


def checkmark(engine, width, height, size):
    x, y = width/2, height/2
    result = _layer(engine, "checkmark", width, height,
                    (x-size*0.42, y, x-size*0.1, y+size*0.3, x+size*0.43, y-size*0.32), 1.9, "line")
    engine._canvas.tag_raise("checkmark")
    return result


def scrollbar(engine, width, height, radius, spacing, start, end, orientation):
    changed = _layer(engine, "border_parts", width, height, (0, 0, width, height), 0)
    if orientation == "vertical":
        bounds = (spacing, spacing+(height-2*spacing)*start, width-spacing-0.25, spacing+(height-2*spacing)*end)
    else:
        bounds = (spacing+(width-2*spacing)*start, spacing, spacing+(width-2*spacing)*end, height-spacing-0.25)
    changed |= _layer(engine, "scrollbar_parts", width, height, bounds, radius)
    engine._canvas.tag_lower("border_parts")
    return changed


def slider(engine, width, height, radius, border, length, button_radius, value, orientation):
    button_radius = min(button_radius, width/2, height/2)
    changed = rounded(engine, width, height, radius, border)
    changed |= _layer(engine, "progress_parts", width, height, (border, border, width-border-0.25, height-border-0.25),
                       max(0, radius-border), clip=(0, 0, width*value, height))
    button_width = min(width-4, max(height-4, length+button_radius*2-4))
    x = 2+max(0, width-button_width-4)*value
    changed |= _layer(engine, "slider_parts", width, height, (x, 2, x+button_width, height-2), button_radius)
    engine._canvas.tag_raise("slider_parts")
    return changed


def install():
    from customtkinter.windows.widgets.core_rendering import CTkCanvas, DrawEngine
    if getattr(CTkCanvas, "_reliane_smooth", False):
        return
    original = CTkCanvas.itemconfig
    def itemconfig(canvas, tag, *args, **kwargs):
        layers = getattr(canvas, "_reliane_layers", {})
        layer = layers.get(tag) if isinstance(tag, str) else next((v for v in layers.values() if v["id"] == tag), None)
        if layer and ("fill" in kwargs or "outline" in kwargs):
            color = kwargs.get("fill", kwargs.get("outline"))
            if layer.get("color") != color:
                layer["color"] = color
                _paint(canvas, layer)
            return
        return original(canvas, tag, *args, **kwargs)
    CTkCanvas.itemconfig = itemconfig
    CTkCanvas._reliane_smooth = True
    DrawEngine.draw_rounded_rect_with_border = rounded
    DrawEngine.draw_rounded_rect_with_border_vertical_split = split
    DrawEngine.draw_dropdown_arrow = arrow
    DrawEngine.draw_checkmark = checkmark
    DrawEngine.draw_rounded_scrollbar = scrollbar
    DrawEngine.draw_rounded_slider_with_border_and_button = slider
