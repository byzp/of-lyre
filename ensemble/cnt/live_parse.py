#!/usr/bin/env python3
import struct
from collections import defaultdict
from typing import Optional, Any
import threading
from scapy.all import sniff, Raw, conf
import snappy
import OverField_pb2
import f
import logging
import traceback

WATCH_MSG_ID = 1936
flow_buffers = defaultdict(bytearray)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _default_put(out_queue, item):
    if out_queue is None:
        print(item)
    else:
        out_queue.appendleft(item)


def process_flow_buffer(flow_key, out_queue: Optional[Any] = None):
    buf = flow_buffers[flow_key]
    processed = 0
    while True:
        # need at least 2 bytes for header length
        if len(buf) < 2:
            break

        # parse header length with protection
        try:
            header_len = struct.unpack(">H", buf[0:2])[0]
        except Exception as e:
            logger.exception(
                "Failed to unpack header length; dropping first byte to resync"
            )
            # drop one byte to try to resync stream
            try:
                del buf[0]
            except Exception:
                # if deletion fails for any reason, break to avoid busy-loop
                break
            continue

        # ensure full header is present
        if len(buf) < 2 + header_len:
            break

        header_data = bytes(buf[2 : 2 + header_len])
        packet_head = OverField_pb2.PacketHead()

        # parse header proto safely
        try:
            packet_head.ParseFromString(header_data)
        except Exception as e:
            logger.exception(
                "Error parsing PacketHead; dropping first 2+header_len bytes to resync"
            )
            # If header parsing fails, drop the bytes we attempted to parse and continue
            try:
                del buf[: 2 + header_len]
            except Exception:
                break
            continue

        total_needed = 2 + header_len + getattr(packet_head, "body_len", 0)
        if len(buf) < total_needed:
            # wait for more data
            break

        body_data = bytes(buf[2 + header_len : 2 + header_len + packet_head.body_len])

        # consume the whole packet from buffer
        try:
            del buf[:total_needed]
        except Exception:
            # If deletion fails, avoid infinite loop
            logger.exception(
                "Failed to delete processed bytes from buffer; aborting processing loop"
            )
            break

        processed += 1

        # decompress if flagged
        if getattr(packet_head, "flag", 0) == 1:
            try:
                body_data = snappy.uncompress(body_data)
            except Exception:
                logger.exception("Failed to uncompress body; skipping this packet")
                # skip this packet and continue processing next
                continue

        head_summary = {
            "msg_id": getattr(packet_head, "msg_id", None),
            "body_len": getattr(packet_head, "body_len", None),
            "flag": getattr(packet_head, "flag", None),
        }

        if getattr(packet_head, "msg_id", None) == WATCH_MSG_ID:
            chat = OverField_pb2.ChatMsgNotice()
            try:
                chat.ParseFromString(body_data)
            except Exception:
                logger.exception(
                    "Failed to parse ChatMsgNotice body; skipping this chat packet"
                )
                continue

            item = {
                "type": "ChatMsgNotice",
                "flow": flow_key,
                "packet_head": head_summary,
                "chat_text": str(chat),
                "raw_body": body_data,
            }
            try:
                print(str(chat))
                with open("log.txt", "a") as file:
                    file.write(str(chat))
            except Exception:
                # printing shouldn't crash processing
                logger.exception("Failed to print chat object")

            # if the chat message starts with '#', attempt lookup
            try:
                if str(chat.msg.text)[:1] == "#":
                    res = f.find_most_similar_file_hash(str(chat.msg.text[1:]))
                    if res is not None:
                        _default_put(out_queue, {"hash": res, "name": "manual"})
            except Exception:
                logger.exception("Error handling '#' command in chat text")

    return processed


def pkt_callback(
    pkt,
    ip_filter,
    port_filter,
    out_queue: Optional[Any] = None,
    stop_event: Optional[threading.Event] = None,
):
    if stop_event is not None and stop_event.is_set():
        return False
    if not pkt.haslayer(Raw):
        return
    ip_layer = pkt.getlayer("IP")
    src_ip = ip_layer.src
    dst_ip = ip_layer.dst
    sport = getattr(pkt, "sport", None)
    dport = getattr(pkt, "dport", None)
    if not (
        (src_ip == ip_filter or dst_ip == ip_filter)
        and (sport == port_filter or dport == port_filter)
    ):
        return
    payload = bytes(pkt[Raw].load)
    if len(payload) == 0:
        return
    flow_key = (src_ip, dst_ip, sport, dport)
    flow_buffers[flow_key].extend(payload)

    # protect processing from unexpected exceptions
    try:
        process_flow_buffer(flow_key, out_queue=out_queue)
    except Exception:
        logger.exception(
            "Unhandled exception in process_flow_buffer for flow %s", flow_key
        )


def start_sniffer(
    iface: str,
    ip: str,
    port: int,
    out_queue: Optional[Any] = None,
    bpf: Optional[str] = None,
    promisc: bool = False,
    stop_event: Optional[threading.Event] = None,
):
    bpf_filter = f"tcp and host {ip} and port {port}"
    if bpf:
        bpf_filter = f"({bpf_filter}) and ({bpf})"
    conf.sniff_promisc = bool(promisc)

    def _stop_filter(pkt):
        return stop_event is not None and stop_event.is_set()

    def _prn_wrapper(pkt):
        return pkt_callback(
            pkt,
            ip_filter=ip,
            port_filter=port,
            out_queue=out_queue,
            stop_event=stop_event,
        )

    sniff(
        iface=iface,
        filter=bpf_filter,
        prn=_prn_wrapper,
        store=0,
        stop_filter=_stop_filter,
    )


def stop_sniffer(stop_event: threading.Event):
    if stop_event is not None:
        stop_event.set()
