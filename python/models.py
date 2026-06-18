from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class SensorReading(db.Model):
    __tablename__ = 'sensor_readings'

    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.Float, nullable=False, index=True)
    data = db.Column(db.JSON)
    flags = db.Column(db.JSON)

    def to_dict(self):
        result = {'id': self.id, 'ts': self.ts, 'flags': self.flags or []}
        result.update(self.data or {})
        return result


class Alert(db.Model):
    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.Float, nullable=False, index=True)
    flags = db.Column(db.JSON)

    def to_dict(self):
        return {'id': self.id, 'ts': self.ts, 'flags': self.flags or []}


class AppSetting(db.Model):
    __tablename__ = 'app_settings'

    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.JSON)
