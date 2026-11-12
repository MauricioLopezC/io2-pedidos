"""Referencias cerradas para una o varias personas y límites del régimen estable."""

import pytest

from pedidos.colas import erlang_c


def test_mm1():
    assert erlang_c(3, 6, 1) == pytest.approx({
        "utilizacion": 0.5, "probabilidad_espera": 0.5,
        "espera_media_min": 10, "total_medio_min": 20,
        "cola_media": 0.5, "sistema_medio": 1,
    })


def test_sin_demanda():
    medidas = erlang_c(0, 6, 2)
    assert medidas["probabilidad_espera"] == medidas["utilizacion"] == 0
    assert medidas["total_medio_min"] == 10


@pytest.mark.parametrize("parametros", [(-1, 1, 2), (1, 0, 2), (1, 1, 0), (1, 1, 1.5),
                                         (float("nan"), 2, 3), (2, 1, 2), (3, 1, 2)])
def test_parametros_invalidos_o_inestables(parametros):
    with pytest.raises(ValueError):
        erlang_c(*parametros)
