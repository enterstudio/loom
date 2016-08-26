'use strict';

angular
    .module('loom.services')
    .service('DataService', DataService)

DataService.$inject = ['$http'];

function DataService($http) {
    /* DataService retrieves and caches data from the server. */
    
    this.setActiveRun = setActiveRun;
    this.setActiveTemplate = setActiveTemplate;
    this.setActiveFile = setActiveFile;
    this.getAllActive = getAllActive;
    this.getRunRequests = getRunRequests;
    this.getTemplates = getTemplates;
    this.getImportedFiles = getImportedFiles;
    this.getResultFiles = getResultFiles;
    this.getLogFiles = getLogFiles;

    var activeData = {};
    
    function getAllActive() {
	return activeData;
    };

    function setActiveRun(runId) {
	return $http.get('/api/workflow-runs/' + runId + '/')
            .then(function(response) {
		activeData.run = response.data;
            });
    };

    function setActiveTemplate(templateId) {
	return $http.get('/api/workflows/' + templateId + '/')
            .then(function(response) {
		activeData.template = response.data;
            });
    };

    function setActiveFile(fileId) {
	return $http.get('/api/files/' + fileId + '/')
            .then(function(response) {
		activeData.file = response.data;
            });
    };

    function getRunRequests() {
	return $http.get('/api/run-requests/')
	    .then(function(response) {
		return response.data;
	    });
    };

    function getTemplates() {
	return $http.get('/api/imported-workflows/')
	    .then(function(response) {
		return response.data;
	    });
    };

    function getImportedFiles() {
	return $http.get('/api/imported-files/')
	    .then(function(response) {
		return response.data;
	    });
    };
    function getResultFiles() {
	return $http.get('/api/result-files/')
	    .then(function(response) {
		return response.data;
	    });
    };
    function getLogFiles() {
	return $http.get('/api/log-files/')
	    .then(function(response) {
		return response.data;
	    });
    };
};
