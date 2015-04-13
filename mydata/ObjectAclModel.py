import requests
import json
import urllib

from logger.Logger import logger
from UserModel import UserProfileModel


class ObjectAclModel():

    def __init__(self, settingsModel=None, objectAclJson=None):
        self.settingsModel = settingsModel
        self.objectAclJson = objectAclJson

    def GetJson(self):
        return self.objectAclJson

    @staticmethod
    def ShareExperimentWithUser(experiment, user):
        """
        Grants full ownership of experiment to user.
        """
        logger.debug("\nSharing via ObjectACL with username \"" +
                     user.GetUsername() + "\"...\n")

        settingsModel = experiment.GetSettingsModel()
        myTardisUrl = settingsModel.GetMyTardisUrl()
        myTardisDefaultUsername = settingsModel.GetUsername()
        myTardisDefaultUserApiKey = settingsModel.GetApiKey()

        objectAclJson = {
            "pluginId": "django_user",
            "entityId": str(user.GetId()),
            "content_object": experiment.GetResourceUri(),
            "object_id": experiment.GetId(),
            "aclOwnershipType": 1,
            "isOwner": True,
            "canRead": True,
            "canWrite": True,
            "canDelete": False,
            "effectiveDate": None,
            "expiryDate": None}

        headers = {"Authorization": "ApiKey " +
                   myTardisDefaultUsername + ":" +
                   myTardisDefaultUserApiKey,
                   "Content-Type": "application/json",
                   "Accept": "application/json"}
        url = myTardisUrl + "/api/v1/objectacl/"
        response = requests.post(headers=headers, url=url,
                                 data=json.dumps(objectAclJson))
        if response.status_code == 201:
            logger.debug("Shared experiment with user " +
                         user.GetUsername() + ".")
        else:
            logger.debug(url)
            logger.debug(response.text)
            logger.debug("response.status_code = " +
                         str(response.status_code))
            if response.status_code == 401:
                message = "Couldn't create ObjectACL for " \
                          "experiment \"%s\"." % experiment.GetTitle()
                message += "\n\n"
                message += "Please ask your MyTardis administrator " \
                           "to check the permissions of the \"%s\" " \
                           "user account." % myTardisDefaultUsername
                raise Unauthorized(message)
            elif response.status_code == 404:
                message = "Couldn't create ObjectACL for " \
                          "experiment \"%s\"." % experiment.GetTitle()
                message += "\n\n"
                message += "A 404 (Not Found) error occurred while " \
                           "attempting to create the ObjectACL.\n\n" \
                           "Please ask your MyTardis administrator " \
                           "to check that a User Profile record " \
                           "exists for the \"%s\" user account." \
                           % myTardisDefaultUsername
                raise DoesNotExist(message, modelClass=UserProfileModel)
            raise

    @staticmethod
    def ShareExperimentWithGroup(experiment, group):
        """
        Grants read access to experiment to group.
        """
        logger.debug("\nSharing via ObjectACL with group \"" +
                     group.GetName() + "\"...\n")

        settingsModel = experiment.GetSettingsModel()
        myTardisUrl = settingsModel.GetMyTardisUrl()
        myTardisDefaultUsername = settingsModel.GetUsername()
        myTardisDefaultUserApiKey = settingsModel.GetApiKey()

        objectAclJson = {
            "pluginId": "django_group",
            "entityId": str(group.GetId()),
            "content_object": experiment.GetResourceUri(),
            "object_id": experiment.GetId(),
            "aclOwnershipType": 1,
            "isOwner": True,
            "canRead": True,
            "canWrite": True,
            "canDelete": False,
            "effectiveDate": None,
            "expiryDate": None}

        headers = {"Authorization": "ApiKey " +
                   myTardisDefaultUsername + ":" +
                   myTardisDefaultUserApiKey,
                   "Content-Type": "application/json",
                   "Accept": "application/json"}
        url = myTardisUrl + "/api/v1/objectacl/"
        response = requests.post(headers=headers, url=url,
                                 data=json.dumps(objectAclJson))
        if response.status_code == 201:
            logger.debug("Shared experiment with group " +
                         group.GetName() + ".")
        else:
            logger.debug(url)
            logger.debug(response.text)
            logger.debug("response.status_code = " +
                         str(response.status_code))
            if response.status_code == 401:
                message = "Couldn't create ObjectACL for " \
                          "experiment \"%s\"." % experiment.GetTitle()
                message += "\n\n"
                message += "Please ask your MyTardis administrator " \
                           "to check the permissions of the \"%s\" " \
                           "user account." % myTardisDefaultUsername
                raise Unauthorized(message)
            elif response.status_code == 404:
                message = "Couldn't create ObjectACL for " \
                          "experiment \"%s\"." % experiment.GetTitle()
                message += "\n\n"
                message += "A 404 (Not Found) error occurred while " \
                           "attempting to create the ObjectACL.\n\n" \
                           "Please ask your MyTardis administrator " \
                           "to check that a User Profile record " \
                           "exists for the \"%s\" user account." \
                           % myTardisDefaultUsername
                raise DoesNotExist(message, modelClass=UserProfileModel)
            raise
