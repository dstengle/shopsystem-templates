Feature: on a version-tag release, the shopsystem-templates release workflow dispatches the bc-launcher repository

  @scenario_hash:26ca8a14e01db50c @bc:shopsystem-templates
  Scenario: on a version-tag release of shopsystem-templates, its release workflow emits a repository_dispatch to the bc-launcher repository
    Given the shopsystem-templates source repository
    And a tag named "v0.2.0" is pushed to its "main" branch
    When the shopsystem-templates release workflow associated with that tag push runs to successful completion
    Then the workflow performs a "repository_dispatch" API call targeting the "shopsystem-bc-launcher" repository
    And that dispatch call carries a credential authorized to dispatch to the bc-launcher repository
