from geoflow.verification import verify


def test_acceptance_suite():
    report = verify()
    assert report["passed"], report
