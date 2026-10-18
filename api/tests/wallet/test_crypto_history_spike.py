"""Tests do núcleo PURO do spike de histórico (m4, Fase 6) — sem rede.

Cobre o veredito de recuperabilidade, a lacuna permanente da KuCoin e a redação de
segredos no relatório (nenhum endereço/chave pode vazar na saída).
"""

from __future__ import annotations

from scripts.spikes import crypto_history_spike as spike


class TestBaseVerdict:
    def test_cex_yes(self) -> None:
        assert spike.base_verdict("binance") == "yes"

    def test_onchain_partial(self) -> None:
        assert spike.base_verdict("ethereum") == "partial"
        assert spike.base_verdict("solana") == "partial"
        assert spike.base_verdict("defi") == "partial"

    def test_hyperevm_no_history_source(self) -> None:
        assert spike.base_verdict("hyperevm") == "no"

    def test_kucoin_permanent_gap(self) -> None:
        assert spike.base_verdict("kucoin") == "no"


class TestRecoverability:
    def test_base_no_is_no(self) -> None:
        p = spike.Probe("x", "e", True, count=99)
        assert spike.recoverability("no", p) == "no"

    def test_missing_probe_is_no(self) -> None:
        assert spike.recoverability("partial", None) == "no"

    def test_failed_probe_is_no(self) -> None:
        assert spike.recoverability("yes", spike.Probe("x", "e", False)) == "no"

    def test_zero_events_is_no(self) -> None:
        assert spike.recoverability("partial", spike.Probe("x", "e", True, count=0)) == "no"

    def test_ok_with_events_keeps_base(self) -> None:
        p = spike.Probe("x", "e", True, count=5)
        assert spike.recoverability("yes", p) == "yes"
        assert spike.recoverability("partial", p) == "partial"


class TestRedaction:
    def test_redacts_evm_address(self) -> None:
        s = "tx para 0x1234567890abcdef1234567890ABCDEF12345678 ok"
        assert "0x1234567890abcdef1234567890ABCDEF12345678" not in spike.redact(s)
        assert "[redacted]" in spike.redact(s)

    def test_redacts_64hex_key(self) -> None:
        key = "a" * 64
        assert key not in spike.redact(f"asset id {key}")

    def test_redacts_bech32_btc(self) -> None:
        addr = "bc1q" + "q" * 38
        assert addr not in spike.redact(f"saldo em {addr}")

    def test_report_does_not_leak_secret_in_note(self) -> None:
        """Um endereço numa note de sonda não pode aparecer no relatório renderizado."""
        secret = "0xDEADBEEFdeadbeefDEADBEEFdeadbeef12345678"
        probes = {"evm-eth": spike.Probe("evm-eth", "tokentx", False, note=f"timeout em {secret}")}
        held = [{"asset": "ETH", "custody": "ethereum", "protocol": None}]
        report = spike.render_report(held, probes)
        assert secret not in report
        assert "ETH" in report  # o ativo aparece


class TestAssetSourceKey:
    def test_defi_pendle_to_arbitrum(self) -> None:
        assert spike._asset_source_key("defi", "pendle_v2") == "evm-arb"

    def test_defi_hylo_to_solana(self) -> None:
        assert spike._asset_source_key("defi", "hylo") == "solana"

    def test_hyperevm_has_no_source(self) -> None:
        assert spike._asset_source_key("hyperevm", None) is None
