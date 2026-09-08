"""Dispatch for bounded, private BIOS diagnostic phases."""

from __future__ import annotations

from avpe.native_event_flag_probe import probe_event_flag_invalid_id
from avpe.native_entry_address_probe import probe_invalid_entry_address
from avpe.native_gs_h_param_probe import probe_gs_h_param_output
from avpe.native_osd_config_probe import probe_osd_config_output
from avpe.native_interrupt_handler_probe import probe_interrupt_handler_invalid_id
from avpe.native_alarm_probe import probe_alarm_invalid_id
from avpe.native_cop0_probe import probe_cop0_registers
from avpe.native_osd_config2_probe import probe_osd_config2_output
from avpe.native_semaphore_probe import probe_semaphore_lifecycle
from avpe.native_sif_dma_probe import probe_invalid_sif_dma
from avpe.native_sif_query_probe import probe_sif_registers
from avpe.native_system_query_probe import probe_system_queries
from avpe.native_thread_probe import probe_thread_control_invalid_id, probe_thread_invalid_id


def run_diagnostic_phase(
    port: int, deadline: float, phase: str
) -> tuple[dict[str, object], str, str] | None:
    if phase == "semaphore":
        return (
            probe_semaphore_lifecycle(port, deadline),
            "statefile_to_diagnostic_semaphore",
            "invalid_id_create_poll_signal_poll_delete",
        )
    if phase == "event-flag-negative":
        return (
            probe_event_flag_invalid_id(port, deadline),
            "statefile_to_diagnostic_event_flag_negative",
            "invalid_id_event_flag_service_calls",
        )
    if phase == "interrupt-handler-negative":
        return (
            probe_interrupt_handler_invalid_id(port, deadline),
            "statefile_to_diagnostic_interrupt_handler_negative",
            "invalid_id_interrupt_handler_service_calls",
        )
    if phase == "thread-negative":
        return (
            probe_thread_invalid_id(port, deadline),
            "statefile_to_diagnostic_thread_negative",
            "invalid_id_thread_service_calls",
        )
    if phase == "thread-control-negative":
        return (
            probe_thread_control_invalid_id(port, deadline),
            "statefile_to_diagnostic_thread_control_negative",
            "invalid_id_thread_control_service_calls",
        )
    if phase == "alarm-negative":
        return (
            probe_alarm_invalid_id(port, deadline),
            "statefile_to_diagnostic_alarm_negative",
            "invalid_id_alarm_service_calls",
        )
    if phase == "system-query":
        return (
            probe_system_queries(port, deadline),
            "statefile_to_diagnostic_system_query",
            "grounded_ee_system_queries",
        )
    if phase == "sif-query":
        return (
            probe_sif_registers(port, deadline),
            "statefile_to_diagnostic_sif_query",
            "grounded_sif_register_queries",
        )
    if phase == "entry-address-negative":
        return (
            probe_invalid_entry_address(port, deadline),
            "statefile_to_diagnostic_entry_address_negative",
            "invalid_get_entry_address_token",
        )
    if phase == "sif-dma-negative":
        return (
            probe_invalid_sif_dma(port, deadline),
            "statefile_to_diagnostic_sif_dma_negative",
            "invalid_sif_dma_status_token",
        )
    if phase == "osd-config-output":
        return (
            probe_osd_config_output(port, deadline),
            "statefile_to_diagnostic_osd_config_output",
            "grounded_osd_output_buffer",
        )
    if phase == "gs-h-param-output":
        return (
            probe_gs_h_param_output(port, deadline),
            "statefile_to_diagnostic_gs_h_param_output",
            "grounded_gs_h_param_output_buffers",
        )
    if phase == "osd-config2-output":
        return (
            probe_osd_config2_output(port, deadline),
            "statefile_to_diagnostic_osd_config2_output",
            "grounded_osd_config2_output_buffer",
        )
    if phase == "cop0-query":
        return (
            probe_cop0_registers(port, deadline),
            "statefile_to_diagnostic_cop0_query",
            "grounded_cop0_register_snapshot",
        )
    return None
