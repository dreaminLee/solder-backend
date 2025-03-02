# # from db_connection import db
# from extends import db
#
#
# class User(db.Model):
#     __tablename__ = 'user'
#
#     UserID = db.Column(db.String(100), primary_key=True)  # 对应 UserID
#     UserIC = db.Column(db.String(100))  # 对应 UserIC
#     UserName = db.Column(db.String(100), nullable=False)  # 对应 UserName
#     Password = db.Column(db.String(100), nullable=False)  # 对应 Password
#     UserGrade = db.Column(db.Integer, nullable=False)  # 对应 UserGrade
#     ModifyDateTime = db.Column(db.DateTime)  # 对应 ModifyDateTime
#     Fingerprint1 = db.Column(db.Text)  # 对应 Fingerprint1
#     Fingerprint2 = db.Column(db.Text)  # 对应 Fingerprint2
#     Fingerprint3 = db.Column(db.Text)  # 对应 Fingerprint3
#
#     def to_dict(self):
#         return {
#             'user_id': self.UserID,
#             'user_ic': self.UserIC,
#             'user_name': self.UserName,
#             'password': self.Password,
#             'user_grade': self.UserGrade,
#             'modify_date_time': self.ModifyDateTime,
#             'fingerprint1': self.Fingerprint1,
#             'fingerprint2': self.Fingerprint2,
#             'fingerprint3': self.Fingerprint3,
#         }