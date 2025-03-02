# import nfc
#
#
# def read():
#     def on_connect(tag):
#         print("Card UID: {}".format(tag.identifier.hex()))
#         return False  # 断开连接
#     clf = nfc.ContactlessFrontend('usb')
#     clf.connect(rdwr={'on-connect': on_connect})
#
#
# def write():
#     def on_connect(tag):
#         if tag.writeable:
#             print("Writing to card...")
#             tag.write('example_data')  # 写入数据
#             print("Data written successfully.")
#         else:
#             print("Card is not writable.")
#         return False
#     clf = nfc.ContactlessFrontend('usb')
#     clf.connect(rdwr={'on-connect': on_connect})
#
# if __name__ == "__main__":
#     read()

import msvcrt

print("按下一个键：")
char = msvcrt.getch()  # 读取单个字符
print(f"你按下了: {char.decode('utf-8')}")

