import pyatspi
import pygtk
pygtk.require("2.0")
import gtk
import signal
import gobject
import highlighter
import gtk.gdk
import string
import rsvg
import cairo
import gconf

# TODO: abstract out the concept of changing timer length handling the edge case
if gtk.pygtk_version < (2, 14, 0):
    print "PyGtk 2.14.0 or later required"
    raise SystemExit


# represents the current app we're scanning
class App:
    def __inti__(self):
        pass


# the UI for the scanner
class ScannerApp:
    def __init__(self):
#        self.builder = gtk.Builder()
#        self.builder.add_from_file("ui-scan-demo.ui") # TODO check for error
#        self.mainWindow = self.builder.get_object("window") # TODO check for None
#        self.fasterButton = self.builder.get_object("faster_button")
#        self.slowerButton = self.builder.get_object("slower_button")
#        self.opacityScale = self.builder.get_object("opacity_scale")
#        self.builder.connect_signals(self)

        self.current_delay = 1500
        self.timer_increment = 100
        self.max_delay = 4000
        self.min_delay = 200
        self.timer_id = gobject.timeout_add(self.current_delay, self.highlight_next)

        self.ui_index1 = self.ui_index2 = 0

#        self.mainWindow.show_all()

    def get_ooowriter_rows(self):
        desktop = pyatspi.Registry.getDesktop(0)
        sofficeIndex = ooowriterIndex = -1
        for i in range(desktop.childCount):
            try:
                item = desktop.getChildAtIndex(i)
                if item.name == "soffice" and item.getRoleName() == "application":
                    for j in range(item.childCount):
                        sofficeWindow = item.getChildAtIndex(j)
                        if sofficeWindow.name.endswith("Writer") and sofficeWindow.getRoleName() == "frame":
                            sofficeIndex, ooowriterIndex = i, j
            except LookupError:
                pass
            except AttributeError:
                pass

        # if we found OOOWriter then get references to the UI that we want to scan over
        # start by getting the rows
        if sofficeIndex >= 0 and ooowriterIndex >= 0:
            ooowriterWindowWDec = desktop.getChildAtIndex(sofficeIndex).getChildAtIndex(ooowriterIndex)
            ooowriterWindow = ooowriterWindowWDec.getChildAtIndex(0)
            assert ooowriterWindow.getRoleName() == "root pane"
            self.ui = self._get_main_rows(ooowriterWindow)

    def _get_main_rows(self, root):
        row = []
        for i in range(root.childCount):
            rootItem = root.getChildAtIndex(i)
            roleName = rootItem.getRoleName()
            if roleName == "menu bar":
                row.append(rootItem)
            elif roleName == "panel" and rootItem.childCount > 0:
                for j in range(rootItem.childCount):
                    panelItem = rootItem.getChildAtIndex(j)
                    row.append(panelItem)
            elif roleName == "statusbar":
                row.append(rootItem)
        return row

    def _get_sub_rows(self, root):
        row = [root]
        for i in range(root.childCount):
            rootItem = root.getChildAtIndex(i)
            roleName = rootItem.getRoleName()
            states = rootItem.getState().getStates()
            if roleName != "separator" and pyatspi.STATE_SENSITIVE in states:
                row.append(rootItem)
        return row

    def highlight_next(self):
        ch = ComponentHighlighter()
        ch.highlight(self.current_delay, self.ui[self.ui_index1%len(self.ui)])
        self.ui_index1 = self.ui_index1 + 1;

        #print "advance_to_next", self.current_delay, self.timer_id
        return True

    def on_slower_button_pressed(self, widget):
        if gobject.source_remove(self.timer_id):
            self.current_delay += self.timer_increment
            self.timer_id = gobject.timeout_add(self.current_delay, self.highlight_next)
            if self.current_delay == self.min_delay + self.timer_increment:
                self.fasterButton.set_sensitive(True)
            elif self.current_delay == self.max_delay:
                widget.set_sensitive(False)
        else:
            # TODO: could be handled better
            print "WARNING - lost \"Slower\" button event"

    def on_faster_button_pressed(self, widget):
        if gobject.source_remove(self.timer_id):
            self.current_delay -= self.timer_increment
            self.timer_id = gobject.timeout_add(self.current_delay, self.highlight_next)
            if self.current_delay == self.min_delay:
                widget.set_sensitive(False)
            elif self.current_delay == self.max_delay - self.timer_increment:
                self.slowerButton.set_sensitive(True)
        else:
            # TODO: could be handled better
            print "WARNING - lost \"Faster\" button event"

    def on_slower_button_activate(self, widget):
        self.on_slower_button_pressed(widget)

    def on_faster_button_activate(self, widget):
        self.on_faster_button_pressed(widget)

    def on_window_delete_event(self, widget, event):
        gobject.source_remove(self.timer_id)
        gtk.main_quit()
        
    def on_key_down(self, event):
        if event.event_string == "Control_R":
            acc = self.ui[self.ui_index1%len(self.ui) - 1]
#            if self.ui_index1%len(self.ui) - 1 == 0:
#                self.ui = self._get_sub_rows(acc.parent)
#            else:
            self.ui = self._get_sub_rows(acc)
            self.ui_index1 = 0
            try:
                action = acc.queryAction()
                for i in range(action.nActions):
                    if action.getName(i) == "click":
                        action.doAction(i)
                        break
            except NotImplementedError:
                pass

# Defines convenience classes representing tree nodes and bag objects.
#
# @author: Peter Parente
# @author: Eitan Isaacson
# @organization: IBM Corporation
# @copyright: Copyright (c) 2006, 2007 IBM Corporation
# @license: BSD
#
# All rights reserved. This program and the accompanying materials are made 
# available under the terms of the BSD which accompanies this distribution, and 
# is available at U{http://www.opensource.org/licenses/bsd-license.php}

MAX_BLINKS = 6

def parseColorString(color_string):
  '''
  Parse a string representation of a 24-bit color, and a 8 bit alpha mask.

  @param color_string: String in the format: #rrbbggaa.
  @type color_string: string

  @return: A color string in the format of #rrggbb, and an opacity value 
  of 0.0 to 1.0
  @rtype: tuple of string and float.
  '''
  return color_string[:-2], long(color_string[-2:], 16) / 255.0

cl = gconf.client_get_default()
BORDER_COLOR, BORDER_ALPHA = parseColorString('#ff0000ff')

FILL_COLOR, FILL_ALPHA = parseColorString('#ff00006f')

class Bag(object):
  '''
  Bag class for converting a dictionary to an object with attributes.
  '''
  def __init__(self, **kwargs):
    self.__dict__.update(kwargs)

  def __str__(self):
    return ', '.join(vars(self).keys())

class ComponentHighlighter(gobject.GObject):
  '''
  Node class that contains convient references to accessibility information 
  for the currently selected node. A L{Node} instance will emit an 
  'accessible-changed' signal when L{update} is called with a new accessible.

  @ivar desktop: The desktop accessible. It holds references to all the 
  application L{Accessibility.Accessible}s
  @type desktop: L{Accessibility.Accessible}
  @ivar acc: The currently selected accessible.
  @type acc: L{Accessibility.Accessible}
  @ivar extents: The extents of a given accessible.
  @type extents: L{Bag}
  '''
  __gsignals__ = {'accessible-changed' :
                  (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   (gobject.TYPE_PYOBJECT,)),
                  'blink-done' :
                  (gobject.SIGNAL_RUN_FIRST,
                   gobject.TYPE_NONE,
                   ())}
  def __init__(self):
    #self.desktop = pyatspi.Registry.getDesktop(0)
    self.acc = None
    #self.extents = None
    self.tree_path = None
    gobject.GObject.__init__(self)

  def update(self, acc):
    '''
    Updates the information in this node for the given accessible including 
    a reference to the accessible and its extents. Also emit the 
    'accessible-changed' signal.

    @param acc: An accessible.
    @type acc: L{Accessibility.Accessible}
    '''
    if not acc or self.isMyApp(acc):
      return
    self.acc = acc
    self.extents = Bag(x = 0, y = 0, width = 0, height = 0)
    try:
      i = acc.queryComponent()
    except NotImplementedError:
      pass
    else:
      if isinstance(i, pyatspi.Accessibility.Component):
        self.extents = i.getExtents(pyatspi.DESKTOP_COORDS)
    self.tree_path = None
    if acc != self.desktop:
        # Don't highlight the entire desktop, it gets annoying.
        self.highlight()
    self.emit('accessible-changed', acc)

  def updateToPath(self, app_name, path):
    '''
    Update the node with a new accessible by providing a tree path 
    in an application.
    
    @param app_name: Application name.
    @type app_name: string
    @param path: The accessible path in the application.
    @type path: list of integer
    '''
    acc = pyatspi.findDescendant(
      self.desktop,
      lambda x: x.name.lower() == app_name.lower(),
      breadth_first = True)
    if acc is None: return
    while path:
      child_index = path.pop(0)
      try:
        acc = acc[child_index]
      except IndexError:
        return
    self.update(acc)

  def highlight(self, duration, acc):
    if not acc: # or self.isMyApp(acc):
      return
    extents = Bag(x = 0, y = 0, width = 0, height = 0)
    try:
      i = acc.queryComponent()
    except NotImplementedError:
      pass
    else:
      if isinstance(i, pyatspi.Accessibility.Component):
          extents = i.getExtents(pyatspi.DESKTOP_COORDS)
   # if acc == self.desktop:
        # Don't highlight the entire desktop, it gets annoying.
        #return
    if extents is None or \
          0 in (extents.width, extents.height) or \
          - 0x80000000 in (extents.x, extents.y):
      return
    ah = _HighLight(extents.x, extents.y,
                    extents.width, extents.height,
                    FILL_COLOR, FILL_ALPHA, BORDER_COLOR, BORDER_ALPHA,
                    2.0, 0)
    ah.highlight(duration)

  def blinkRect(self, times = MAX_BLINKS):
    '''
    Blink a rectangle on the screen using L{extents} for position and size.

    @param times: Maximum times to blink.
    @type times: integer
    '''
    if self.extents is None or \
          - 0x80000000 in (self.extents.x, self.extents.y):
      return
    self.max_blinks = times
    self.blinks = 0
    # get info for drawing highlight rectangles
    display = gtk.gdk.display_get_default()
    screen = display.get_default_screen()
    self.root = screen.get_root_window()
    self.gc = self.root.new_gc()
    self.gc.set_subwindow(gtk.gdk.INCLUDE_INFERIORS)
    self.gc.set_function(gtk.gdk.INVERT)
    self.gc.set_line_attributes(3, gtk.gdk.LINE_ON_OFF_DASH, gtk.gdk.CAP_BUTT,
                                gtk.gdk.JOIN_MITER)
    self.inv = gtk.Invisible()
    self.inv.set_screen(screen)
    gobject.timeout_add(30, self._drawRectangle)

  def _drawRectangle(self):
    '''
    Draw a rectangle on the screen using L{extents} for position and size.
    '''
    # draw a blinking rectangle 
    if self.blinks == 0:
      self.inv.show()
      self.inv.grab_add()
    self.root.draw_rectangle(self.gc, False,
                             self.extents.x,
                             self.extents.y,
                             self.extents.width,
                             self.extents.height)
    self.blinks += 1
    if self.blinks >= self.max_blinks:
      self.inv.grab_remove()
      self.inv.destroy()
      self.emit('blink-done')
      return False
    return True

class _HighLight(gtk.Window):
  '''
  Highlight box class. Uses compositing when available. When not, it does
  transparency client-side.
  '''
  _svg = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg"> 
  <rect
       style="fill:$fill;fill-opacity:$fill_opacity;fill-rule:evenodd;stroke:$stroke;stroke-width:2;stroke-linecap:butt;stroke-linejoin:miter;stroke-miterlimit:4;stroke-dasharray:none;stroke-opacity:$stroke_opacity"
       id="highlight"
       width="$width"
       height="$height"
       x="$x"
       y="$y"
       rx="2"
       ry="2" />
</svg>
"""
  def __init__(self, x, y, w, h,
               fill_color, fill_alpha,
               stroke_color, stroke_alpha,
               stroke_width, padding = 0):

    # Initialize window.
    gtk.Window.__init__(self, gtk.WINDOW_POPUP)

    # Normalize position for stroke and padding.
    self.x, self.y = x - padding, y - padding
    self.w, self.h = w + padding * 2, h + padding * 2

    # Determine if we are compositing.
    self._composited = self.is_composited()
    if self._composited:
      # Prepare window for transparency.
      screen = self.get_screen()
      colormap = screen.get_rgba_colormap()
      self.set_colormap(colormap)
    else:
      # Take a screenshot for compositing on the client side.
      self.root = gtk.gdk.get_default_root_window().get_image(
        self.x, self.y, self.w, self.h)

    # Place window, and resize it, and set proper properties.
    self.set_app_paintable(True)
    self.set_decorated(False)
    self.set_keep_above(True)
    self.move(self.x, self.y)
    self.resize(self.w, self.h)
    self.set_accept_focus(False)
    self.set_sensitive(False)

    # Create SVG with given parameters.
    offset = stroke_width / 2.0
    self.svg = string.Template(self._svg).substitute(
      x = offset, y = offset,
      width = int(self.w - stroke_width), height = int(self.h - stroke_width),
      fill = fill_color,
      stroke_width = stroke_width,
      stroke = stroke_color,
      fill_opacity = fill_alpha,
      stroke_opacity = stroke_alpha)

    # Connect "expose" event.
    self.connect("expose-event", self._onExpose)

  def highlight(self, duration = 500):
    if duration > 0:
      gobject.timeout_add(duration, lambda w: w.destroy(), self)
      self.show_all()
    else:
      self.destroy()

  def _onExpose(self, widget, event):
    svgh = rsvg.Handle()
    try:
      svgh.write(self.svg)
    except (gobject.GError, KeyError, ValueError), ex:
      print 'Error reading SVG for display: %s\r\n%s', ex, self.svg
      svgh.close()
      return
    svgh.close()

    if not self._composited:
      # Draw the screengrab of the underlaying window, and set the drawing
      # operator to OVER.
      self.window.draw_image(self.style.black_gc, self.root,
                             event.area.x, event.area.y,
                             event.area.x, event.area.y,
                             event.area.width, event.area.height)
      cairo_operator = cairo.OPERATOR_OVER
    else:
      cairo_operator = cairo.OPERATOR_SOURCE
    cr = self.window.cairo_create()
    cr.set_source_rgba(1.0, 1.0, 1.0, 0.0)
    cr.set_operator(cairo_operator)
    cr.paint()

    svgh.render_cairo(cr)
    del svgh

if __name__ == '__main__':
    # allow <ctr>-c to exit app
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = ScannerApp()
    app.get_ooowriter_rows()
    pyatspi.Registry.registerKeystrokeListener(app.on_key_down,
                                               mask = None,
                                               kind=(pyatspi.KEY_PRESSED_EVENT,))
    
    gtk.main()
