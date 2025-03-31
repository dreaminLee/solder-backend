import xml.etree.ElementTree as ET
import requests
from datetime import datetime
def send_log_in(url, user, pwd, deviceid,reelid):
    """
    向MES发送锡膏入柜记录
    :param url: MES url
    :param user: 用户名
    :param pwd: 密码
    :param deviceid:锡膏设备编号
    :param reelid: 锡膏码,支持单个条码,逗号分隔的多个条码或者列表形式的多个条码
    """
    return send_log(url, user, pwd,deviceid,opcode=0, reelid=reelid)


def send_log_rewarm(url, user, pwd, deviceid,reelid):
    """
    向MES发送锡膏开始回温记录

    :param url: MES url
    :param user: 用户名
    :param pwd: 密码
    :param deviceid:锡膏设备编号
    :param reelid: 锡膏码
    """
    return send_log(url, user, pwd,deviceid,opcode=1, reelid=reelid)


def send_log_recycle(url, user, pwd,deviceid, reelid):
    """
    向MES发送锡膏回收记录

    :param url: MES url
    :param user: 用户名
    :param pwd: 密码
    :param deviceid:锡膏设备编号
    :param reelid: 锡膏码
    """
    return send_log(url, user, pwd,deviceid, opcode=3, reelid=reelid)


def send_log_stir(url, user, pwd, deviceid,reelid, time):
    """
    向MES发送锡膏开始搅拌记录

    :param url: MES url
    :param user: 用户名
    :param pwd: 密码
    :param deviceid:锡膏设备编号
    :param reelid: 锡膏码
    :param time: 时间
    """
    return send_log(url, user, pwd,deviceid, opcode=2, reelid=reelid, time=time)



def send_log(url, user, pwd,deviceid, **kwargs) -> dict:
    """
    向MES发送记录基础函数
    send_log把user、pwd、kwargs按照协议组装成XML，用http post发送到MES url
    MES返回值按照协议组装成dict返回

    :param url: MES url
    :param user: 用户名
    :param pwd: 密码
    :param deviceid:锡膏设备编号
    :param kwargs: 参数
    """
    # 初始化返回结构
    result = {
        'Status': 1,
        'OperDate': None,
        'Error': '未知错误'
    }
    try:
        # 参数校验
        opcode = str(kwargs.get('opcode', ''))
        time = kwargs.get('time', '')

        # 验证操作类型
        if opcode not in {'0', '1', '2', '3'}:
            raise ValueError("无效的操作类型")

        # 验证设备编号
        if not deviceid:
            raise ValueError("必须提供设备编号")

        # 处理锡膏条码
        reel_ids = []
        if opcode == '0':  # 入库操作
            reel_source = kwargs.get('reelids', kwargs.get('reelid', []))
            if isinstance(reel_source, str):
                reel_ids = reel_source.split(',')
            elif isinstance(reel_source, list):
                reel_ids = reel_source
            else:
                reel_ids = [str(reel_source)]

            if not reel_ids:
                raise ValueError("入库需要至少一个锡膏条码")
        else:  # 其他操作
            reelid = kwargs.get('reelid', '')
            if not reelid:
                raise ValueError("必须提供锡膏条码")
            # 判断条码是否只有一个
            if isinstance(reelid, list):
                reelid_list = reelid
            else:
                reelid_list = reelid.split(',') if reelid else []
            reelid_list = [rid.strip() for rid in reelid_list if rid.strip()]
            if len(reelid_list) != 1:
                raise ValueError("必须提供一个锡膏条码")

            reel_ids = reelid_list

        # 验证搅拌时间
        if opcode == 2 and not time:
            raise ValueError("搅拌操作需要时长参数")

        # 构建XML请求
        root = ET.Element('STD_IN')
        ET.SubElement(root, 'EDI_user').text = user
        ET.SubElement(root, 'EDI_pwd').text = pwd
        ET.SubElement(root, 'ObjectID').text = 'Solder_Paste_Operation'
        ET.SubElement(root, 'Operation').text = opcode

        sfb_file = ET.SubElement(root, 'sfb_file')
        ET.SubElement(sfb_file, 'Device').text = deviceid

        if opcode == 2:
            ET.SubElement(sfb_file, 'Time').text = str(time)

        reelids_elem = ET.SubElement(sfb_file, 'Reelids')
        for rid in reel_ids:
            ET.SubElement(reelids_elem, 'Reelid').text = rid.strip()

        # 生成XML数据
        xml_data = ET.tostring(root, encoding='utf-8', xml_declaration=True)

        # 发送HTTP请求
        headers = {'Content-Type': 'application/xml'}
        response = requests.post(url, data=xml_data, headers=headers, timeout=10)
        response.raise_for_status()

        # 解析响应XML
        ns = {'': ''}  # 禁用命名空间处理
        resp_root = ET.fromstring(response.content)
        result['Status'] = resp_root.findtext('Status', 1).strip()
        result['OperDate'] = resp_root.findtext('OperDate', '').strip()
        result['Error'] = resp_root.findtext('Error', '').strip()

    except requests.exceptions.RequestException as e:
        result['Error'] = f"网络请求失败: {str(e)}"
    except ET.ParseError as e:
        result['Error'] = f"响应解析失败: {str(e)}"
    except ValueError as e:
        result['Error'] = f"参数验证失败: {str(e)}"
    except Exception as e:
        result['Error'] = f"系统异常: {str(e)}"

    return result

# 测试
# if __name__ == "__main__":
#     print(send_log_in("http://127.0.0.1:4523/m1/3977342-0-default/MES","1","1","1",['123','456']))
#     print(send_log_rewarm("http://127.0.0.1:4523/m1/3977342-0-default/MES", "1", "1", "1", ['123','456']))
#     print(send_log_rewarm("http://127.0.0.1:4523/m1/3977342-0-default/MES", "1", "1", "1", '456'))
#     print(send_log_stir("http://127.0.0.1:4523/m1/3977342-0-default/MES", "1", "1", "1", '456',time=3600))
