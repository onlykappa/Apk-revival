"""Line icons drawn with QPainter on a 24-unit grid, in a Fluent-like outline style."""
from __future__ import annotations
from PySide6.QtCore import QPointF,QRectF,Qt
from PySide6.QtGui import QColor,QIcon,QPainter,QPainterPath,QPen,QPixmap

def _draw(p,name):
    line=lambda *pts:[p.drawLine(QPointF(*pts[i]),QPointF(*pts[i+1])) for i in range(len(pts)-1)]
    if name=='library':
        for x,y in [(3,3),(13,3),(3,13),(13,13)]:p.drawRoundedRect(QRectF(x,y,8,8),2,2)
    elif name=='add':line((12,4),(12,20));line((4,12),(20,12))
    elif name=='setup':
        p.drawEllipse(QPointF(12,12),3.2,3.2);path=QPainterPath()
        import math
        for n in range(16):
            angle=math.pi*2*n/16;radius=9 if n%2==0 else 6.6
            point=QPointF(12+radius*math.cos(angle),12+radius*math.sin(angle))
            path.moveTo(point) if n==0 else path.lineTo(point)
        path.closeSubpath();p.drawPath(path)
    elif name=='updates':
        p.drawArc(QRectF(4,4,16,16),40*16,280*16);line((17,3.5),(18.6,7.2),(14.8,8.2))
    elif name=='fullscreen':
        for a,b,c in [((4,9),(4,4),(9,4)),((15,4),(20,4),(20,9)),((20,15),(20,20),(15,20)),((9,20),(4,20),(4,15))]:line(a,b,c)
    elif name=='play':
        path=QPainterPath(QPointF(8,5));path.lineTo(19,12);path.lineTo(8,19);path.closeSubpath();p.drawPath(path)
    elif name=='spark':
        path=QPainterPath(QPointF(12,3));path.quadTo(12.8,11.2,21,12);path.quadTo(12.8,12.8,12,21);path.quadTo(11.2,12.8,3,12);path.quadTo(11.2,11.2,12,3);p.drawPath(path)
    elif name=='package':
        line((12,3),(20,7.5),(20,16.5),(12,21),(4,16.5),(4,7.5),(12,3));line((4,7.5),(12,12),(20,7.5));line((12,12),(12,21))
    elif name=='phone':
        p.drawRoundedRect(QRectF(6.5,2.5,11,19),2.5,2.5);line((10.5,18.2),(13.5,18.2))
    elif name=='window':
        p.drawRoundedRect(QRectF(3,4.5,18,15),2,2);line((3,9),(21,9))
    elif name=='link':
        p.drawRoundedRect(QRectF(2.5,8.5,10,7),3.5,3.5);p.drawRoundedRect(QRectF(11.5,8.5,10,7),3.5,3.5)
    elif name=='info':
        p.drawEllipse(QPointF(12,12),9,9);line((12,11),(12,16.5));p.drawPoint(QPointF(12,7.8))
    elif name=='key':
        p.drawEllipse(QPointF(8,12),4,4);line((12,12),(21,12),(21,15));line((17.5,12),(17.5,14.5))
    elif name=='download':
        line((12,4),(12,15));line((7.5,10.5),(12,15),(16.5,10.5));line((5,19.5),(19,19.5))
    elif name=='gamepad':
        path=QPainterPath();path.addRoundedRect(QRectF(2.5,7,19,11),5.5,5.5);p.drawPath(path);line((6.5,12.5),(10.5,12.5));line((8.5,10.5),(8.5,14.5))
        p.drawPoint(QPointF(15.5,11.5));p.drawPoint(QPointF(17.5,13.5))
    elif name=='refresh':
        p.drawArc(QRectF(4,4,16,16),60*16,300*16);line((20,4.5),(20,9.5),(15,9.5))
    elif name=='stop':p.drawRoundedRect(QRectF(6,6,12,12),2,2)
    elif name=='more':
        for x in (6,12,18):p.drawPoint(QPointF(x,12))
    elif name=='folder':
        path=QPainterPath(QPointF(3,6.5));path.lineTo(9,6.5);path.lineTo(11,8.5);path.lineTo(21,8.5);path.lineTo(21,18.5);path.lineTo(3,18.5);path.closeSubpath();p.drawPath(path)

def pixmap(name,color='#ffffff',size=20,ratio=2.0):
    pm=QPixmap(int(size*ratio),int(size*ratio));pm.fill(Qt.GlobalColor.transparent);pm.setDevicePixelRatio(ratio)
    p=QPainter(pm);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.scale(size/24,size/24)
    width=3.2 if name=='more' else 1.6
    pen=QPen(QColor(color),width);pen.setCapStyle(Qt.PenCapStyle.RoundCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);p.setPen(pen);p.setBrush(Qt.BrushStyle.NoBrush)
    if name in ('info',):
        _draw(p,name);pen.setWidthF(2.6);p.setPen(pen);p.drawPoint(QPointF(12,7.8))
    elif name=='gamepad':
        _draw(p,name);pen.setWidthF(2.4);p.setPen(pen);p.drawPoint(QPointF(15.5,11.5));p.drawPoint(QPointF(17.5,13.5))
    else:_draw(p,name)
    p.end();return pm

def icon(name,color='#ffffff',size=20):
    result=QIcon(pixmap(name,color,size))
    result.addPixmap(pixmap(name,'#7a7a7a',size),QIcon.Mode.Disabled)
    return result
