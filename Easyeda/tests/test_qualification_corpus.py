from Easyeda.catalogue import CATALOGUE
from Easyeda.donor_source import EasyedaDonorSource, bundled_source_pack
from Easyeda.qualification_corpus import ARCHETYPES, build_circuit


def test_qualification_catalogue_has_30_archetypes_and_full_physical_coverage() -> None:
    source = EasyedaDonorSource(bundled_source_pack())
    assert len(ARCHETYPES) == 30
    circuits = [build_circuit(archetype, 1, source) for archetype in ARCHETYPES]
    covered = {
        component["kind"]
        for circuit in circuits
        for component in circuit["components"]
    }
    expected = {
        kind
        for kind, entry in CATALOGUE.items()
        if entry.selector.pcb_required
    }
    assert expected <= covered
    assert all(len(circuit["components"]) <= 32 for circuit in circuits)
    assert all(circuit["routing"]["mode"] == "combination" for circuit in circuits)


def test_corpus_inputs_explicitly_account_for_every_donor_pin() -> None:
    source = EasyedaDonorSource(bundled_source_pack())
    circuit = build_circuit(ARCHETYPES[10], 1, source)
    assert all(
        not net["name"].startswith("GUESS_")
        for net in circuit["nets"]
    )
    for component in circuit["components"]:
        packet = source.resolve(CATALOGUE[component["kind"]])
        assert set(component["pins"]) == {pin.number for pin in packet.pins}
